import yaml
import indigo
import logging

import pycarwings.connection
import pycarwings.userservice
import pycarwings.vehicleservice

import distance_scale

CONNECTED_VALUE_MAP = {
	'CONNECTED': True,
	'NOT_CONNECTED'  : False
}

CHARGING_VALUE_MAP = {
	'NORMAL_CHARGING': True,
	'CHARGING': True, # is this one valid? I made it up.
	'NOT_CHARGING'  : False
}

distance_format = distance_scale.Miles()

class IndigoLeaf:
	def __init__(self, dev, plugin):
		self.dev = dev
		self.vin = dev.pluginProps["address"]
		self.plugin = plugin
		self.log = logging.getLogger('indigo.nissanleaf.plugin')

	def start_charging(self):
		self.plugin.vehicleservice.start_charge(self.vin)

	def start_climate_control(self):
		self.plugin.vehicleservice.start_ac_now(self.vin)

	def request_status(self):
		self.log.info("requesting status for %s" % self.vin)
		self.plugin.vehicleservice.request_status(self.vin)

	def update_status(self):
		self.log.info("updating status for %s" % self.vin)
		status = self.plugin.userservice.get_latest_status(self.vin)
		self.log.debug("status: %s" % yaml.dump(status))

	 	lbs = status.latest_battery_status
		self.dev.updateStateOnServer(key="batteryCapacity", value=lbs.battery_capacity)
		self.dev.updateStateOnServer(key="batteryRemainingCharge", value=lbs.battery_remaining_amount)

		try:
			is_connected = CONNECTED_VALUE_MAP[lbs.plugin_state]
		except KeyError:
			self.log.error(u"Unknown connected state: '%s'" % lbs.plugin_state)
			is_connected = True # probably
		self.dev.updateStateOnServer(key="connected", value=is_connected)

		distance_format.report(self.dev, "cruisingRangeACOff", lbs.cruising_range_ac_off)
		distance_format.report(self.dev, "cruisingRangeACOn", lbs.cruising_range_ac_on)

		self.dev.updateStateOnServer(key="chargingStatus", value=lbs.battery_charging_status)
		try:
			is_charging = CHARGING_VALUE_MAP[lbs.battery_charging_status]
		except KeyError:
			self.log.error(u"Unknown charging state: '%s'" % lbs.battery_charging_status)
			is_charging = True # probably
		self.dev.updateStateOnServer(key="charging", value=is_charging)

		# may be None if we're fast charging(?)
		if lbs.time_required_to_full:
			trickle_time_m = float(lbs.time_required_to_full.days * 1440) + (float(lbs.time_required_to_full.seconds) / 60)
			self.dev.updateStateOnServer(key="timeToFullTrickle", value=trickle_time_m, decimalPlaces=0,
										uiValue=str(lbs.time_required_to_full))
		else:
			self.dev.updateStateOnServer(key="timeToFullTrickle", value=-1, decimalPlaces=0, uiValue="-")

		# may be None if we're trickle charging
		if lbs.time_required_to_full_L2:
			l2_time_m = float(lbs.time_required_to_full_L2.days * 1440) + (float(lbs.time_required_to_full_L2.seconds) / 60)
			self.dev.updateStateOnServer(key="timeToFullL2", value=l2_time_m, decimalPlaces=0,
										uiValue=str(lbs.time_required_to_full_L2))
		else:
			self.dev.updateStateOnServer(key="timeToFullL2", value=-1, decimalPlaces=0, uiValue="-")

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

		self.log.info("finished updating status for %s" % self.vin)
