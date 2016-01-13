#! /usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import json
import indigo
import logging
import time
import pycarwings.connection
import pycarwings.userservice
import pycarwings.vehicleservice


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

class IndigoLeaf:
	def __init__(self, dev, userservice, vehicleservice):
		self.dev = dev
		self.vin = dev.pluginProps["vin"]
		self.userservice = userservice
		self.vehicleservice = vehicleservice
		self.log = logging.getLogger('indigo.nissanleaf.plugin')

	def request_status(self):
		self.log.info("requesting status for %s" % self.vin)
		self.vehicleservice.request_status(self.vin)

	def update_status(self):
		self.log.info("updating status for %s" % self.vin)
		status = self.userservice.get_latest_status(self.vin)
		"""
		batteryCapacity : 0 (integer)
     batteryRemainingCharge : 0 (integer)
     chargingStatus : false (bool)
     climateControl : off (on/off bool)
     connectedStatus : false (bool)
     cruisingRangeACOff : 0 (integer)
     cruisingRangeACOn : 0 (integer)
     timeToFullL2 : 0 (integer)
     timeToFullTrickle : 0 (integer)
	 """
		self.dev.updateStateOnServer(key="batteryCapacity", value=status.latest_battery_status.battery_capacity)
		self.dev.updateStateOnServer(key="batteryRemainingCharge", value=status.latest_battery_status.battery_remaining_amount)
		self.log.debug("finished updating status for %s" % self.vin)


class Plugin(indigo.PluginBase):

	def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
		indigo.PluginBase.__init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs)
		self.debug = DEBUG

		logHandler = IndigoLoggingHandler(self)

		self.log = logging.getLogger('indigo.nissanleaf.plugin')
		self.log.addHandler(logHandler)

		if DEBUG:
			self.log.setLevel(logging.DEBUG)
		else:
			self.log.setLevel(logging.WARNING)

		self.leaves = []


	def __del__(self):
		indigo.PluginBase.__del__(self)

	def get_vins(self, filter="", valuesDict=None, typeId="", targetId=0):
		if self.connection.logged_in:
			return self.vins

		self.log.error("not logged in")
		return []


	def startup(self):
		self.debugLog(u"startup called")
		self.connection = pycarwings.connection.Connection(self.pluginPrefs['username'], self.pluginPrefs['password'])
		self.userservice = pycarwings.userservice.UserService(self.connection)
		self.vehicleservice = pycarwings.vehicleservice.VehicleService(self.connection)

		status = self.userservice.login_and_get_status()

		if self.connection.logged_in:
			vin = status.user_info.vin
			self.log.info( "logged in, vin: %s, nickname: %s" % (vin, status.user_info.nickname))
			self.vins = [(vin, status.user_info.nickname)]
		else:
			self.log.error( "Log in invalid, please try again")

	def shutdown(self):
		self.debugLog(u"shutdown called")


	def deviceStartComm(self, dev):
#		self.debugLog('deviceStartComm: %s' % dev)
		self.leaves.append(IndigoLeaf(dev, self.userservice, self.vehicleservice))

	def deviceStopComm(self, dev):
		self.leaves = [
			l for l in self.leaves
				if l.vin != dev.pluginProps["vin"]
		]

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
