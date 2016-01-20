import yaml
import indigo
import logging

import pycarwings.connection
import pycarwings.userservice
import pycarwings.vehicleservice
from pycarwings.connection import CarwingsError

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

DISTANCE_SCALE_MAP = {
	"k" : distance_scale.Kilometers(),
	"m" : distance_scale.Miles()
}

log = logging.getLogger('indigo.nissanleaf.plugin')

class IndigoLeaf:

	# class variables
	connection = None
	userservice = None
	vehicleservice = None
	distance_format = distance_scale.Miles()

	vins = []

	@staticmethod
	def setup(username, password, region):
		IndigoLeaf.connection = pycarwings.connection.Connection(username, password, region)
		IndigoLeaf.userservice = pycarwings.userservice.UserService(IndigoLeaf.connection)
		IndigoLeaf.vehicleservice = pycarwings.vehicleservice.VehicleService(IndigoLeaf.connection)

	@staticmethod
	def use_distance_scale(s):
		log.debug("using distance scale '%s'" % s)
		IndigoLeaf.distance_format = DISTANCE_SCALE_MAP[s]

	@staticmethod
	def login():
		log.debug("logging in to %s region" % IndigoLeaf.connection.region)
		log.debug("url: %s" % IndigoLeaf.connection.BASE_URL)
		status = IndigoLeaf.userservice.login_and_get_status()
		if IndigoLeaf.connection.logged_in:
			vin = status.user_info.vin
			log.info( "logged in, vin: %s, nickname: %s" % (vin, status.user_info.nickname))
			IndigoLeaf.vins = [(vin, status.user_info.nickname)]
		else:
			log.error( "Log in invalid, please try again")

	@staticmethod
	def get_vins():
		return IndigoLeaf.vins

	def __init__(self, dev, plugin):
		self.dev = dev
		if "address" in dev.pluginProps:
			# version 0.0.3
			self.vin = dev.pluginProps["address"]
		elif "vin" in dev.pluginProps:
			# version 0.0.1
			self.vin = dev.pluginProps["vin"]
		else:
			log.error("couldn't find a property with the VIN: %s" % dev.pluginProps)


	def start_charging(self):
		if not self.connection.logged_in:
			self.login()
		try:
			self.vehicleservice.start_charge(self.vin)
		except CarwingsError:
			log.warn("error starting charging; logging in again and retrying")
			self.login()
			self.vehicleservice.start_charge(self.vin)

	def start_climate_control(self):
		if not self.connection.logged_in:
			self.login()
		try:
			self.vehicleservice.start_ac_now(self.vin)
		except CarwingsError:
			log.warn("error starting climate contro; logging in again and retrying")
			self.login()
			self.vehicleservice.start_ac_now(self.vin)

	def request_status(self):
		if not self.connection.logged_in:
			self.login()
		log.info("requesting status for %s" % self.vin)
		try:
			self.vehicleservice.request_status(self.vin)
		except CarwingsError:
			log.warn("error requesting status; logging in again and retrying")
			self.login()
			self.vehicleservice.request_status(self.vin)

	def update_status(self):
		if not self.connection.logged_in:
			self.login()
		log.info("updating status for %s" % self.vin)
		try:
			status = self.userservice.get_latest_status(self.vin)
		except CarwingsError:
			log.warn("error getting latest status; logging in again and retrying")
			self.login()
			status = self.userservice.get_latest_status(self.vin)

		log.debug("status: %s" % yaml.dump(status))

	 	lbs = status.latest_battery_status
		self.dev.updateStateOnServer(key="batteryCapacity", value=lbs.battery_capacity)
		self.dev.updateStateOnServer(key="batteryRemainingCharge", value=lbs.battery_remaining_amount)

		try:
			is_connected = CONNECTED_VALUE_MAP[lbs.plugin_state]
		except KeyError:
			log.error(u"Unknown connected state: '%s'" % lbs.plugin_state)
			is_connected = True # probably
		self.dev.updateStateOnServer(key="connected", value=is_connected)

		IndigoLeaf.distance_format.report(self.dev, "cruisingRangeACOff", lbs.cruising_range_ac_off)
		IndigoLeaf.distance_format.report(self.dev, "cruisingRangeACOn", lbs.cruising_range_ac_on)

		self.dev.updateStateOnServer(key="chargingStatus", value=lbs.battery_charging_status)
		try:
			is_charging = CHARGING_VALUE_MAP[lbs.battery_charging_status]
		except KeyError:
			log.error(u"Unknown charging state: '%s'" % lbs.battery_charging_status)
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
			log.debug("using 'charger on' icon")
			self.dev.updateStateImageOnServer(indigo.kStateImageSel.BatteryChargerOn)
		elif is_connected:
			log.debug("using 'charger off' icon")
			self.dev.updateStateImageOnServer(indigo.kStateImageSel.BatteryCharger)
		elif pct >= 87.5:
			log.debug("using 'battery high' icon")
			self.dev.updateStateImageOnServer(indigo.kStateImageSel.BatteryLevelHigh)
		elif pct >= 62.5:
			log.debug("using 'battery 75' icon")
			self.dev.updateStateImageOnServer(indigo.kStateImageSel.BatteryLevel75)
		elif pct > 37.5:
			log.debug("using 'battery 50' icon")
			self.dev.updateStateImageOnServer(indigo.kStateImageSel.BatteryLevel50)
		elif pct > 15:
			log.debug("using 'battery 25' icon")
			self.dev.updateStateImageOnServer(indigo.kStateImageSel.BatteryLevel25)
		else:
			log.debug("using 'battery low' icon")
			self.dev.updateStateImageOnServer(indigo.kStateImageSel.BatteryLevelLow)

		log.info("finished updating status for %s" % self.vin)
