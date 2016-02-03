#! /usr/bin/env python
# -*- coding: utf-8 -*-

import indigo
import logging
from urllib2 import HTTPError

from indigo_leaf import IndigoLeaf
from pycarwings.connection import CarwingsError


DEBUGGING_ENABLED_MAP = {
	"y" : True,
	"n" : False
}

class IndigoLoggingHandler(logging.Handler):
	def __init__(self, p):
		 logging.Handler.__init__(self)
		 self.plugin = p

	def emit(self, record):
		if record.levelno < 20:
			self.plugin.debugLog(record.getMessage())
		elif record.levelno < 40:
			indigo.server.log(record.getMessage())
		else:
			self.plugin.errorLog(record.getMessage())

class Plugin(indigo.PluginBase):

	def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
		indigo.PluginBase.__init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs)

		logHandler = IndigoLoggingHandler(self)

		self.log = logging.getLogger('indigo.nissanleaf.plugin')
		logging.getLogger("pycarwings").addHandler(logHandler)
		self.log.addHandler(logHandler)

		self.leaves = []

	def __del__(self):
		indigo.PluginBase.__del__(self)

	def update_logging(self, is_debug):
		if is_debug:
			self.debug = True
			self.log.setLevel(logging.DEBUG)
			logging.getLogger("pycarwings").setLevel(logging.DEBUG)
			self.log.debug("debug logging enabled")
		else:
			self.log.debug("debug logging disabled")
			self.debug=False
			self.log.setLevel(logging.INFO)
			logging.getLogger("pycarwings").setLevel(logging.INFO)

	def get_vins(self, filter="", valuesDict=None, typeId="", targetId=0):
		return IndigoLeaf.get_vins()

	def start_charging(self, action):
		self.log.debug("charging action: %s" % action)
		self.leaves[0].start_charging()

	def start_climate_control(self, action):
		self.log.debug("climate control action: %s" % action)
		self.leaves[0].start_climate_control()

	def startup(self):
		if "debuggingEnabled" not in self.pluginPrefs:
			# added in 0.0.3
			self.pluginPrefs["debuggingEnabled"] = "n"

		self.update_logging(DEBUGGING_ENABLED_MAP[self.pluginPrefs["debuggingEnabled"]])

		self.log.debug(u"startup called")

		if 'region' not in self.pluginPrefs:
			# added in 0.0.2
			self.pluginPrefs['region'] = 'US'

		if 'distanceUnit' not in self.pluginPrefs:
			# added in ... 0.0.2?
			self.pluginPrefs['distanceUnit'] = 'k'

		IndigoLeaf.use_distance_scale(self.pluginPrefs['distanceUnit'])
		IndigoLeaf.setup(self.pluginPrefs['username'], self.pluginPrefs['password'], self.pluginPrefs['region'])

		# login will happen automatically first time we call the API

	def shutdown(self):
		self.log.debug(u"shutdown called")

	def deviceStartComm(self, dev):
		dev.stateListOrDisplayStateIdChanged() # in case any states added/removed after plugin upgrade

		newProps = dev.pluginProps
		newProps["SupportsBatteryLevel"] = True
		dev.replacePluginPropsOnServer(newProps)

		leaf = IndigoLeaf(dev, self)

		# assume device will be updated on the next loop

		self.leaves.append(leaf)

	def deviceStopComm(self, dev):
		self.leaves = [
			l for l in self.leaves
				if l.vin != dev.pluginProps["address"]
		]

	def validatePrefsConfigUi(self, valuesDict):
		self.log.debug("validatePrefsConfigUi: %s" % valuesDict)
		self.update_logging(bool(valuesDict['debuggingEnabled'] and "y" == valuesDict['debuggingEnabled']))

		IndigoLeaf.use_distance_scale(valuesDict["distanceUnit"])

		if (self.pluginPrefs['region'] != valuesDict['region']) or (self.pluginPrefs['username'] != valuesDict['username']) or (self.pluginPrefs['password'] != valuesDict['password']):
			IndigoLeaf.setup(valuesDict['username'], valuesDict['password'], valuesDict['region'])
			# no need to log in here; that will happen automatically next time we use the service

		return True


	def runConcurrentThread(self):
		try:
			while True:
				try:

					for l in self.leaves:
						l.request_and_update_status(self.sleep)

				except HTTPError as e:
					self.log.error("HTTP error connecting to Nissan's servers; will try again later (%s)" % e)
					self.log.debug(e.read())
				except CarwingsError as e:
					self.log.error("Carwings error connecting to Nissan's servers; will try again later (%s)" % e)

				self.sleep(840)

		except self.StopThread:
			pass	# Optionally catch the StopThread exception and do any needed cleanup.
