import logging
import logging.config
import sys
import traceback

from .hedgehog_app import HedgehogApp


def main():
    logging.config.fileConfig('logging.conf')
    logging.root.root.addHandler(logging.StreamHandler(sys.stdout))

    try:
        HedgehogApp().run()
    except:
        traceback.print_exc(file=sys.stdout)
        raise

if __name__ == '__main__':
    main()