#! /usr/bin/env python
# -*- coding: utf-8 -*-

import indigo
import logging

import pycarwings.connection
import pycarwings.userservice
import pycarwings.vehicleservice

import indigo_leaf

from pycarwings.response import CarwingsError

import distance_scale


DEBUG=True
DISTANCE_SCALE_PLUGIN_PREF="distanceUnit"

DISTANCE_SCALE_MAP = {
	"k" : distance_scale.Kilometers(),
	"m" : distance_scale.Miles()
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

def mapped_plugin_pref_value(pluginPrefs, map, key, default):
	if key in pluginPrefs:
		return map[pluginPrefs[key][0]]
	else:
		return default

class Plugin(indigo.PluginBase):

	def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
		indigo.PluginBase.__init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs)
		self.debug = DEBUG

		logHandler = IndigoLoggingHandler(self)

		self.log = logging.getLogger('indigo.nissanleaf.plugin')
		logging.getLogger("pycarwings").addHandler(logHandler)
		self.log.addHandler(logHandler)

		if DEBUG:
			self.log.setLevel(logging.DEBUG)
			logging.getLogger("pycarwings").setLevel(logging.DEBUG)
		else:
			self.log.setLevel(logging.INFO)
			logging.getLogger("pycarwings").setLevel(logging.INFO)

		self.leaves = []

		indigo_leaf.distance_format = mapped_plugin_pref_value(pluginPrefs, DISTANCE_SCALE_MAP,
			DISTANCE_SCALE_PLUGIN_PREF, distance_scale.Miles())


	def __del__(self):
		indigo.PluginBase.__del__(self)

	def get_vins(self, filter="", valuesDict=None, typeId="", targetId=0):
		if self.connection.logged_in:
			return self.vins

		self.log.error("not logged in")
		return []

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

		self.connection = pycarwings.connection.Connection(self.pluginPrefs['username'], self.pluginPrefs['password'], self.pluginPrefs['region'])
		self.userservice = pycarwings.userservice.UserService(self.connection)
		self.vehicleservice = pycarwings.vehicleservice.VehicleService(self.connection)

#		self.connection.logged_in = True


	def shutdown(self):
		self.debugLog(u"shutdown called")

	def login(self):
		self.log.debug("logging in to %s region" % self.connection.region)
		self.log.debug("url: %s" % self.connection.BASE_URL)
		status = self.userservice.login_and_get_status()
		if self.connection.logged_in:
			vin = status.user_info.vin
			self.log.info( "logged in, vin: %s, nickname: %s" % (vin, status.user_info.nickname))
			self.vins = [(vin, status.user_info.nickname)]
		else:
			self.log.error( "Log in invalid, please try again")


	def deviceStartComm(self, dev):
#		self.debugLog('deviceStartComm: %s' % dev)
		newProps = dev.pluginProps
		newProps["SupportsBatteryLevel"] = True
		dev.replacePluginPropsOnServer(newProps)

		if not self.connection.logged_in:
			self.login()

		leaf = indigo_leaf.IndigoLeaf(dev, self)
#		leaf.update_status()
		self.leaves.append(leaf)

	def deviceStopComm(self, dev):
		self.leaves = [
			l for l in self.leaves
				if l.vin != dev.pluginProps["address"]
		]

	def validatePrefsConfigUi(self, valuesDict):
		indigo_leaf.distance_format = mapped_plugin_pref_value(valuesDict, DISTANCE_SCALE_MAP,
			DISTANCE_SCALE_PLUGIN_PREF, distance_scale.Miles())
		if self.pluginPrefs['region'] != valuesDict['region']:
			self.log.debug("changing region from %s to %s" % (self.pluginPrefs['region'], valuesDict['region']))

			# restart the plugin to use different server
			plugin = indigo.server.getPlugin("com.drjason.nissanleaf")
			plugin.restart(waitUntilDone=False)

		return True


	def runConcurrentThread(self):
		try:
			while True:
				if not self.connection.logged_in:
					self.login()

				for l in self.leaves:
					try:
						l.request_status()
					except CarwingsError:
						# hmm; try logging in again and repeating?
						self.log.warn("error requesting status; logging in again and retrying")
						self.login()
						l.request_status()

				self.sleep(20)

				for l in self.leaves:
					l.update_status()

				self.sleep(900)

		except self.StopThread:
			pass	# Optionally catch the StopThread exception and do any needed cleanup.
