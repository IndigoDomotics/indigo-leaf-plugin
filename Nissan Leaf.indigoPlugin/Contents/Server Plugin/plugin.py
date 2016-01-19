#! /usr/bin/env python
# -*- coding: utf-8 -*-

import indigo
import logging

from indigo_leaf import IndigoLeaf

from pycarwings.response import CarwingsError

DEBUG=True

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
		self.debug = DEBUG

		logHandler = IndigoLoggingHandler(self)

		self.log = logging.getLogger('indigo.nissanleaf.plugin')
		logging.getLogger("pycarwings").addHandler(logHandler)
		self.log.addHandler(logHandler)

		self.update_logging()

		self.leaves = []

	def __del__(self):
		indigo.PluginBase.__del__(self)

	def update_logging(self):
		if DEBUG:
			self.log.setLevel(logging.DEBUG)
			logging.getLogger("pycarwings").setLevel(logging.DEBUG)
		else:
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
		self.debugLog(u"startup called")
		if 'region' not in self.pluginPrefs:
			self.pluginPrefs['region'] = 'US'

		IndigoLeaf.use_distance_scale(self.pluginPrefs["distanceUnit"])
		IndigoLeaf.setup(self.pluginPrefs['username'], self.pluginPrefs['password'], self.pluginPrefs['region'])
		IndigoLeaf.login()

	def shutdown(self):
		self.debugLog(u"shutdown called")

	def deviceStartComm(self, dev):
		newProps = dev.pluginProps
		newProps["SupportsBatteryLevel"] = True
		dev.replacePluginPropsOnServer(newProps)

		leaf = IndigoLeaf(dev, self)
		leaf.update_status()
		self.leaves.append(leaf)

	def deviceStopComm(self, dev):
		self.leaves = [
			l for l in self.leaves
				if l.vin != dev.pluginProps["address"]
		]

	def validatePrefsConfigUi(self, valuesDict):
		IndigoLeaf.use_distance_scale(valuesDict["distanceUnit"])

		if valuesDict['debuggingEnabled'] and "y" == valuesDict['debuggingEnabled']:
			DEBUG = True
		else:
			DEBUG = False

		self.update_logging()

		IndigoLeaf.use_distance_scale(valuesDict["distanceUnit"])

		if (self.pluginPrefs['region'] != valuesDict['region']) or (self.pluginPrefs['username'] != valuesDict['username']) or (self.pluginPrefs['password'] != valuesDict['password']):
			IndigoLeaf.setup(valuesDict['username'], valuesDict['password'], valuesDict['region'])
			IndigoLeaf.login()

		return True


	def runConcurrentThread(self):
		try:
			while True:

				for l in self.leaves:
					l.request_status()

				self.sleep(20)

				for l in self.leaves:
					l.update_status()

				self.sleep(900)

		except self.StopThread:
			pass	# Optionally catch the StopThread exception and do any needed cleanup.
