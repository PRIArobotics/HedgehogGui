import time
import zmq
from hedgehog.client import HedgehogClient

from pyre.zactor import ZActor
from kivy.app import App
from kivy.lang import Builder
from kivy.properties import BooleanProperty, ListProperty, NumericProperty, ObjectProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivymd.label import MDLabel
from kivymd.list import MDList, ILeftBody, TwoLineIconListItem
from kivymd.theming import ThemableBehavior

from hedgehog.utils.discovery.node import Node
from hedgehog.utils import zmq as zmq_utils


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


class HedgehogApp(App):
    service = 'hedgehog_server'

    endpoints = ListProperty()

    def __init__(self):
        super().__init__()
        self.actor = None
        self.controller = None
        self.ctx = zmq.Context.instance()

        # loading kivmd.theming opens a window.
        # defer until App is created
        from kivymd.theming import ThemeManager

        self.theme_cls = ThemeManager()

    def build(self):
        result = super().build()
        self.nav_drawer = Builder.template('HedgehogNavDrawer')
        return result

    def on_start(self):
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
        def actor(ctx, pipe):
            pipe.signal()

            with Node("Hedgehog Client", ctx) as node:
                node.join(self.service)
                time.sleep(0.1)
                node.request_service(self.service)

                def recv_api():
                    command, *args = pipe.recv_multipart()
                    command = command.decode('UTF-8')

                    if command == '$TERM':
                        for socket in list(poller.sockets):
                            poller.unregister(socket)

                def recv_inbox():
                    node.inbox.recv_multipart()
                    peers = node.get_peers(self.service)
                    self.endpoints = sorted({(peer.name, endpoint)
                                             for peer in peers
                                             for endpoint in peer.services[self.service]},
                                            key=lambda endpoint: endpoint[1])

                poller = zmq_utils.Poller()
                poller.register(pipe, zmq.POLLIN, recv_api)
                poller.register(node.inbox, zmq.POLLIN, recv_inbox)

                then = time.time()
                while len(poller.sockets) > 0:
                    timeout = 10000 - int((time.time() - then) * 1000)
                    if timeout <= 0:
                        node.request_service(self.service)
                        then = time.time()
                    else:
                        for _, _, recv in poller.poll(timeout):
                            recv()

        self.actor = ZActor(self.ctx, actor)

    def teardown_actor(self):
        if self.actor is not None:
            self.actor.destroy()
            self.actor = None

    def connect(self, controller):
        if controller == self.controller:
            return

        self.disconnect()

        self.controller = controller
        controller.client = HedgehogClient(controller.endpoint, self.ctx)

    def disconnect(self):
        if self.controller is not None:
            self.controller.disconnect()
            self.controller = None

    def action(self, action):
        if self.client is not None:
            action(self.client)
