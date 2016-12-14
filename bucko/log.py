import logging

logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.INFO)
log = logging.getLogger('bucko')

# Silence requests and paramiko
logging.getLogger('requests').setLevel(logging.WARNING)
logging.getLogger('paramiko').setLevel(logging.WARNING)
