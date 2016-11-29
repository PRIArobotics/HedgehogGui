import time
import zmq
from hedgehog.client import HedgehogClient

from kivy.app import App
from kivy.lang import Builder
from kivy.properties import BooleanProperty, ListProperty, NumericProperty, ObjectProperty, OptionProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivymd.label import MDLabel
from kivymd.list import MDList, ILeftBody, TwoLineIconListItem
from kivymd.theming import ThemableBehavior

from hedgehog.utils.discovery.service_node import ServiceNode
from hedgehog.utils.zmq.actor import Actor, CommandRegistry
from hedgehog.utils.zmq.poller import Poller
from hedgehog.protocol.messages import io


class MotorControl(ThemableBehavior, BoxLayout):
    port = NumericProperty()
    value = NumericProperty()

    def update(self, client):
        client.move(self.port, self.value)


class ServoControl(ThemableBehavior, BoxLayout):
    port = NumericProperty()
    value = NumericProperty()
    active = BooleanProperty(False)

    def update(self, client):
        client.set_servo(self.port, self.active, self.value)


class IOControl(ThemableBehavior, BoxLayout):
    port = NumericProperty()
    value = NumericProperty()

    type = OptionProperty('digital', options=('digital', 'analog', 'output'))
    pull = OptionProperty('pullup', options=('pullup', 'pulldown', 'floating'))
    level = OptionProperty('off', options=('on', 'off'))

    configs = {
        'digital': 0,
        'analog': 0,
        'output': io.OUTPUT,
        'pullup': io.PULLUP,
        'pulldown': io.PULLDOWN,
        'floating': 0,
        'on': io.LEVEL,
        'off': 0,
    }

    def update(self, client):
        flags = self.configs[self.type]
        flags |= self.configs[self.level] if self.type == 'output' else self.configs[self.pull]
        client._send(io.StateAction(self.port, flags))

    def get_update(self, client):
        if self.type == 'digital':
            self.value = 1 if client.get_digital(self.port) else 0
        elif self.type == 'analog':
            self.value = client.get_analog(self.port)


class ControllerIcon(ILeftBody, MDLabel):
    connected = BooleanProperty(False)


class ControllerItem(TwoLineIconListItem):
    name = StringProperty("")
    endpoint = StringProperty("")
    client = ObjectProperty(None, allownone=True)

    def disconnect(self):
        if self.client is not None:
            self.client.close()
            self.client = None


class ControllerList(MDList):
    endpoints = ListProperty()

    def __init__(self, **kwargs):
        super(ControllerList, self).__init__(**kwargs)
        self._endpoints = {}

    def update_endpoints(self):
        for endpoint, widget in list(self._endpoints.items()):
            if endpoint not in self.endpoints:
                widget.disconnect()
                del self._endpoints[endpoint]
                self.remove_widget(widget)
        for index, endpoint in enumerate(self.endpoints):
            if endpoint not in self._endpoints:
                widget = ControllerItem(name=endpoint[0], endpoint=endpoint[1])
                self._endpoints[endpoint] = widget
                self.add_widget(widget, index)


class DiscoveryActor(object):
    def __init__(self, ctx, cmd_pipe, evt_pipe, app):
        self.ctx = ctx
        self.cmd_pipe = cmd_pipe
        self.evt_pipe = evt_pipe
        self.app = app

        self.node = ServiceNode(self.ctx, "Hedgehog Client")
        self.poller = Poller()
        self.register_cmd_pipe()

        self.run()

    def register_cmd_pipe(self):
        registry = CommandRegistry()
        self.poller.register(self.cmd_pipe, zmq.POLLIN, lambda: registry.handle(self.cmd_pipe.recv_multipart()))

        @registry.command(b'$TERM')
        def handle_term():
            self.terminate()

    def terminate(self):
        for socket in list(self.poller.sockets):
            self.poller.unregister(socket)

    def run(self):
        # Signal actor successfully initialized
        self.evt_pipe.signal()

        with self.node:
            self.node.join(self.app.service)
            time.sleep(0.1)
            self.node.request_service(self.app.service)

            def recv_evt_pipe():
                self.node.evt_pipe.recv_multipart()
                peers = self.node.get_peers()
                self.app.endpoints = sorted({(peer.name, endpoint)
                                         for peer in peers if self.app.service in peer.services
                                         for endpoint in peer.services[self.app.service]},
                                        key=lambda endpoint: endpoint[1])
                controller = self.app.controller
                if controller is not None:
                    ident = controller.name, controller.endpoint
                    if ident not in self.app.endpoints:
                        self.app.disconnect()


            self.poller.register(self.node.evt_pipe, zmq.POLLIN, recv_evt_pipe)

            then = time.time()
            while len(self.poller.sockets) > 0:
                timeout = 3000 - int((time.time() - then) * 1000)
                if timeout <= 0:
                    self.node.request_service(self.app.service)
                    then = time.time()
                else:
                    for _, _, handler in self.poller.poll(timeout):
                        handler()


hello_world = \
"""from time import sleep
from hedgehog.client import connect


with connect(emergency=15) as hedgehog:
	print("Hello World")
"""


class HedgehogApp(App):
    service = 'hedgehog_server'

    controller = ObjectProperty(None, allownone=True)
    endpoints = ListProperty()

    def __init__(self):
        super().__init__()
        self.actor = None
        self.nav_drawer = None
        self.ctx = zmq.Context.instance()

        # loading kivmd.theming opens a window.
        # defer until App is created
        from kivymd.theming import ThemeManager

        self.theme_cls = ThemeManager()

    def build(self):
        self.nav_drawer = Builder.template('HedgehogNavDrawer')
        return super().build()

    def on_start(self):
        self.root.editor.editor.text = hello_world
        self.setup_actor()

    def on_stop(self):
        self.disconnect()
        self.teardown_actor()

    def on_resume(self):
        self.setup_actor()

    def on_pause(self):
        self.disconnect()
        self.teardown_actor()

    @property
    def client(self):
        if self.controller is None:
            return None
        if self.controller.client is None:
            self.controller = None
            return None
        return self.controller.client

    def setup_actor(self):
        self.actor = Actor(self.ctx, DiscoveryActor, self)

    def teardown_actor(self):
        if self.actor is not None:
            self.actor.destroy()
            self.actor = None

    def connect(self, controller):
        if controller == self.controller:
            return

        self.disconnect()

        self.controller = controller
        controller.client = HedgehogClient(self.ctx, controller.endpoint)

    def disconnect(self):
        if self.controller is not None:
            self.controller.disconnect()
            self.controller = None

    def execute(self):
        code = self.root.editor.code
        self.root.editor.output = ""

        def do_output(text):
            self.root.editor.output += text

        pid = self.client.execute_process(
                "python",
                on_stdout=lambda _, pid, fileno, chunk: do_output(chunk.decode()),
                on_stderr=lambda _, pid, fileno, chunk: do_output(chunk.decode()),
                on_exit=lambda _, pid, exit_code: do_output("\n  Program finished: {}\n".format(exit_code)))
        self.client.send_process_data(pid, code.encode())
        self.client.send_process_data(pid)

    def action(self, action):
        if self.client is not None:
            action(self.client)
