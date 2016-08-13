import logging.config
import time
import zmq

from .hedgehog_app import HedgehogApp


def main():
    logging.config.fileConfig('logging.conf')

    HedgehogApp().run()

if __name__ == '__main__':
    main()