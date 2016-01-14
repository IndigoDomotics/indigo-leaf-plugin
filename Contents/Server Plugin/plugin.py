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

CONNECTED_VALUE_MAP = {
	'CONNECTED': True,
	'NOT_CONNECTED'  : False
}

CHARGING_VALUE_MAP = {
	'NORMAL_CHARGING': True,
	'CHARGING': True, # is this one valid? I made it up.
	'NOT_CHARGING'  : False
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
		  Nissan Leaf                     !!python/object:pycarwings.response.LatestBatteryStatus
latest_battery_status: !!python/object:pycarwings.response.SmartphoneLatestBatteryStatusResponse
  battery_capacity: !!python/unicode '12'
  battery_charging_status: !!python/unicode 'NOT_CHARGING'
  battery_remaining_amount: !!python/unicode '7'
  cruising_range_ac_off: !!python/unicode '71208.0'
  cruising_range_ac_on: !!python/unicode '70176.0'
  last_battery_status_check_execution_time: 2016-01-13 21:15:36+00:00
  notification_date_and_time: 2016-01-13 21:15:54+00:00
  operation_date_and_time: 2016-01-13 21:15:36+00:00
  operation_result: !!python/unicode 'START'
  plugin_state: !!python/unicode 'NOT_CONNECTED'
  time_required_to_full: !!python/object/apply:datetime.timedelta [0, 41400, 0]
  time_required_to_full_L2: !!python/object/apply:datetime.timedelta [0, 16200, 0]
  """
		"""
     climateControl : off (on/off bool)
	 """
	 	lbs = status.latest_battery_status
		self.dev.updateStateOnServer(key="batteryCapacity", value=lbs.battery_capacity)
		self.dev.updateStateOnServer(key="batteryRemainingCharge", value=lbs.battery_remaining_amount)

		try:
			is_connected = CONNECTED_VALUE_MAP[lbs.plugin_state]
		except KeyError:
			self.log.error(u"Unknown connected state: '%s'" % lbs.plugin_state)
			is_connected = True # probably
		self.dev.updateStateOnServer(key="connectedStatus", value=is_connected)

		no_ac = float(lbs.cruising_range_ac_off) / 1000
		self.dev.updateStateOnServer(key="cruisingRangeACOff", value=no_ac, decimalPlaces=1,
									uiValue=u"%skm" % "{0:.1f}".format(no_ac))
		yes_ac = float(lbs.cruising_range_ac_on) / 1000
		self.dev.updateStateOnServer(key="cruisingRangeACOn", value=yes_ac, decimalPlaces=1,
									uiValue=u"%skm" % "{0:.1f}".format(yes_ac))
		try:
			is_charging = CHARGING_VALUE_MAP[lbs.battery_charging_status]
		except KeyError:
			self.log.error(u"Unknown charging state: '%s'" % lbs.battery_charging_status)
			is_charging = True # probably
		self.dev.updateStateOnServer(key="chargingStatus", value=is_charging)

		# may be None if we're fast charging(?)
		if lbs.time_required_to_full:
			trickle_time_m = float(lbs.time_required_to_full.days * 1440) + (float(lbs.time_required_to_full.seconds) / 60)
			self.dev.updateStateOnServer(key="timeToFullTrickle", value=trickle_time_m, decimalPlaces=0,
										uiValue=str(lbs.time_required_to_full))

		# may be None if we're trickle charging
		if lbs.time_required_to_full_L2:
			l2_time_m = float(lbs.time_required_to_full_L2.days * 1440) + (float(lbs.time_required_to_full_L2.seconds) / 60)
			self.dev.updateStateOnServer(key="timeToFullL2", value=l2_time_m, decimalPlaces=0,
										uiValue=str(lbs.time_required_to_full_L2))

		pct = 100 * float(lbs.battery_remaining_amount) / float(lbs.battery_capacity)
		self.dev.updateStateOnServer(key="batteryLevel", value=pct, decimalPlaces=0,
									uiValue=u"%s%%" % "{0:.0f}".format(pct))

		if is_charging:
			self.log.debug("using 'charger on' icon")
			self.dev.updateStateImageOnServer(indigo.kStateImageSel.BatteryChargerOn)
		elif is_connected:
			self.log.debug("using 'charger off' icon")
			self.dev.updateStateImageOnServer(indigo.kStateImageSel.BatteryCharger)
		elif pct >= 87.5:
			self.log.debug("using 'battery high' icon")
			self.dev.updateStateImageOnServer(indigo.kStateImageSel.BatteryLevelHigh)
		elif pct >= 62.5:
			self.log.debug("using 'battery 75' icon")
			self.dev.updateStateImageOnServer(indigo.kStateImageSel.BatteryLevel75)
		elif pct > 37.5:
			self.log.debug("using 'battery 50' icon")
			self.dev.updateStateImageOnServer(indigo.kStateImageSel.BatteryLevel50)
		elif pct > 15:
			self.log.debug("using 'battery 25' icon")
			self.dev.updateStateImageOnServer(indigo.kStateImageSel.BatteryLevel25)
		else:
			self.log.debug("using 'battery low' icon")
			self.dev.updateStateImageOnServer(indigo.kStateImageSel.BatteryLevelLow)

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
		newProps = dev.pluginProps
		newProps["SupportsBatteryLevel"] = True
		dev.replacePluginPropsOnServer(newProps)

		leaf = IndigoLeaf(dev, self.userservice, self.vehicleservice)
		leaf.update_status()
		self.leaves.append(leaf)

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
