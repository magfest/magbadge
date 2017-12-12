#!/bin/env python3
import settings, logging, argparse, requests, asyncio, websockets
from copy		import deepcopy
from datetime	import datetime
from functools	import partial
from uuid		import UUID
from os			import path, chdir


async def getAttndFromBadge(badge):
	'''Takes a string that can be scanned barcode or a positive number,
	otherwise raises a ValueError, then queries the MAGAPI for the
	associated attendee'''
	if (type(badge) == str and [0] != '~'):
		req = deepcopy(settings.magapi.barcode_lookup)
	else:
		if int(badge) < 0:
			logger.warning('({}) is less than 0'.format(badge))
			raise ValueError('({}) is less than 0'.format(badge))
		req = deepcopy(settings.magapi.lookup)
	req['params'][0] = str(badge)
	kwargs = dict(
		url=getSetting('url'),
		timeout=getSetting('timeout'),
		json=req,
		headers=settings.magapi.headers
	)

	logger.info('Looking up badge {}'.format(badge))
	logger.debug(req)
	futr_resp = loop.run_in_executor(None, partial(requests.post, **kwargs))
	resp = await futr_resp
	logger.info('Server response was HTTP {}'.format(resp.status_code))
	logger.debug(resp.text)

	return resp


async def prcsConnection(sock, path):
	'''Process incoming connections'''
	logger.debug(
		'Client connection opened at {}:{}'.format(*sock.remote_address))
	while sock.open:
		msg = await sock.recv()


def getSetting(name):
	'''Get setting from either debug or runtime scope. If getting setting from
	debug scope, fall back to runtime scope if debug doesn't specify'''
	if args.debug:
		return getattr(settings.debug, name, getattr(settings.runtime, name))
	else:
		return getattr(settings.runtime, name)


def parseargs():
	'''Parses command-line arguments and returns them as a Namespace object'''
	parser = argparse.ArgumentParser()
	parser.add_argument(
		'-V', '--version', action='version',
		version="%(prog)s v{}".format(settings.version))
	parser.add_argument(
		'-e', '--expand-json', action='store_false', dest='minify',
		help='Add newlines and spacing to JSON responses')
	parser.add_argument(
		'-E', '--no-expand-json', action='store_true', dest='minify',
		help='Undo --expand-json')
	parser.add_argument(
		'-v', action='count', default=0, dest='verbose',
		help='Output more verbose info. Specify more than once to increase.')
	parser.add_argument(
		'--verbose', action='store', default=0, type=int, metavar='N',
		help='Specify verbosity level explicitly. Set level to N.')
	parser.add_argument(
		'--debug', action='store_true',
		help='Run with debug settings')
	return parser.parse_args()


def setLogLevel(firstRun=False):
	'''Sets logging level based on the program verbosity state. Only cares
	about the first StreamHandler or FileHandler attached to logger.'''
	rootLogger = logging.getLogger()
	ch = [h for h in rootLogger.handlers if type(h) is logging.StreamHandler][0]
	fh = [h for h in rootLogger.handlers if type(h) is logging.FileHandler][0]
	if not firstRun:
		logger.warning("Changing log level")
	# Set to default levels
	ch.setLevel(logging.WARN)
	fh.setLevel(logging.INFO)
	logging.getLogger("requests").setLevel(logging.WARN)
	logging.getLogger("urllib3").setLevel(logging.WARN)
	if args.verbose == 1:	# Console Info Verbosity
		ch.setLevel(logging.INFO)
	if args.verbose >= 2:	# Debug Verbosity
		ch.setLevel(logging.DEBUG)
		logging.getLogger("requests").setLevel(logging.DEBUG)
		logging.getLogger("urllib3").setLevel(logging.DEBUG)
	if args.verbose >= 3:	# Highest current Verbosity level
		fh.setLevel(logging.DEBUG)


def startup():
	'''Do basic setup for the program. This really should only be run once
	but has some basic tests to prevent double-assignment'''
	chdir(path.dirname(path.abspath(__file__)))
	open(settings.logfile, 'w').close()
	global args, logger, loop
	args = parseargs()
	loop = asyncio.get_event_loop()

	# Set up logging
	conFmt="[%(levelname)8s] %(name)s: %(message)s"
	filFmt="%(asctime)s [%(levelname)8s] %(name)s: %(message)s"
	logger = logging.getLogger(__name__)
	rootLogger = logging.getLogger()
	if len(rootLogger.handlers) is 0:
		rootLogger.setLevel(logging.DEBUG)
		ch = logging.StreamHandler()
		ch.setFormatter(logging.Formatter(conFmt))
		fh = logging.FileHandler(settings.logfile)
		rootLogger.addHandler(ch)
		fh.setFormatter(logging.Formatter(filFmt, "%Y-%m-%d %H:%M:%S"))
		rootLogger.addHandler(fh)
		setLogLevel(True)
		logger.debug('Logging set up.')
	logger.debug('Args state: {}'.format(args))
	logger.info('Badge check midlayer v{} starting on {} ({})'.format(
		settings.version,
		datetime.now().date(),
		datetime.now().date().strftime("%A")))

	# Set up API key
	try:
		with open('apikey.txt') as f:
			settings.magapi.headers['X-Auth-Token'] = str(UUID(f.read().strip()))
	except FileNotFoundError:
		logger.fatal('Could not find API key file, refusing to run.')
		raise SystemExit
	except ValueError:
		logger.fatal('API key not a valid UUID, refusing to run.')
		raise SystemExit

	global server
	try:
		server
	except NameError:
		server = loop.run_until_complete(websockets.serve(
			prcsConnection,
			'localhost',
			getSetting('l_port')))
		logger.info('Now listening for connections on {}:{}'.format(
			'localhost',
			getSetting('l_port')))


if __name__ == '__main__':
	startup()
