import logging

logger = logging.getLogger("client")
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter(
	'[%(levelname)s] %(asctime)s %(name)s::%(module)s::%(lineno)d: %(message)s',
	'%H:%M:%S')

fileLogger = logging.FileHandler('log.txt', mode='w')
fileLogger.setLevel(logging.DEBUG)
fileLogger.setFormatter(formatter)

streamLogger = logging.StreamHandler()
streamLogger.setLevel(logging.DEBUG)
streamLogger.setFormatter(formatter)

logger.addHandler(fileLogger)
logger.addHandler(streamLogger)

logger.info("Start logging")
logger.warning("Warning")
logger.error("Error")
logger.debug("Debugging")
