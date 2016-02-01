import urllib2
from xml.dom import minidom
import logging

BASE_URL = {
    "US" : "https://nissan-na-smartphone-biz.viaaq.com/aqPortal/smartphoneProxy",
    "EU" : "https://nissan-eu-smartphone-biz.viaaq.eu/aqPortal/smartphoneProxy"
}

log = logging.getLogger("pycarwings")

class CarwingsError(Exception):
    pass

class Connection(object):
    """Maintains a connection to CARWINGS, refreshing it when needed"""

    def __init__(self, username, password, region="US"):
        self.username = username
        self.password = password
        self.logged_in = False
        self.set_region(region)
        self.connect()

    def connect(self):
        self.handler = urllib2.HTTPCookieProcessor()
        self.opener = urllib2.build_opener(self.handler)

    def set_region(self, region):
        self.BASE_URL = BASE_URL[region]
        if self.logged_in and self.region != region:
            self.logged_in = False
        self.region = region


    def post_xml(self, service, xml_data, suppress_response=False):
        data = xml_data.toxml()
        log.debug("posting to: %s" % self.BASE_URL)
        log.debug(data)
        request = urllib2.Request("%s%s" % (self.BASE_URL, service),
                                  data,
                                  {'Content-Type': 'text/xml',
                                   'User-Agent': 'NissanLEAF/1.40 CFNetwork/485.13.9 Darwin/11.0.0 pyCW'})
        response = self.opener.open(request)
        log.debug("reading response")
        response_data = response.read()
        log.debug("response read; closing")
        response.close()

        log.debug("processing response")
        if response_data:
            log.debug("response: %s" % response_data)
            ret = minidom.parseString(response_data)

            # check for error response
            error_found = ret.getElementsByTagNameNS('*', "ErrorCode")
            if len(error_found) > 0:
                if error_found and error_found[0] and error_found[0].firstChild:
                    raise CarwingsError(error_found[0].firstChild.data)
                else:
                    raise CarwingsError()

            if suppress_response:
                return True
            else:
                return ret
        else:
            log.debug("empty response")

        if not suppress_response:
            log.warning("no reponse to return; returning True")

        return True



class AuthException(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)
