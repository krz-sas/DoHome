"""
Support for DoHome

Developed by Rave from hogc
"""
import logging
import socket
import json
from datetime import timedelta
from homeassistant.helpers.event import track_time_interval
import homeassistant.util.color as color_util
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ATTR_RGBWW_COLOR,
    LightEntity,
    LightEntityFeature,
    ColorMode
)

from . import (DOHOME_GATEWAY, DoHomeDevice)

EFFECTS_DICT = {
"Colorful gradient": 1,
"red gradient": 2,
"Green gradient": 3,
"blue gradient": 4,
"yellow gradient": 5,
"Cyan gradient": 6,
"Purple gradient": 7,
"White gradient": 8,
"Red strobe": 9,
"Green strobe": 10,
"Blue strobe": 11,
"yellow strobe": 12,
"Red-green gradient": 13,
"red and blue gradient": 14,
"Green-blue gradient": 15,
"Red-green jump": 16,
"Red and blue jump": 17,
"Green-blue transition": 18,
"Red and green strobe": 19,
"red and blue strobe": 20,
"Green and blue strobe": 21,
"Colorful jump": 22,
"Colorful strobe": 23,
"White strobe": 24,
"Three-color gradient": 25,
"Three color jump": 26,
"Three-color strobe": 27
}

_LOGGER = logging.getLogger(__name__)

def setup_platform(hass, config, add_devices, discovery_info=None):
    light_devices = []
    devices = DOHOME_GATEWAY.devices
    for (device_type, device_info) in devices.items():
        for device in device_info:
            _LOGGER.info(device)
            if(device['type'] == '_STRIPE' or device['type'] == '_DT-WYRGB'):
                light_devices.append(DoHomeLight(hass, device))
    
    if(len(light_devices) > 0):
        add_devices(light_devices)


class DoHomeLight(DoHomeDevice, LightEntity):

    def __init__(self, hass, device):

        self._device = device
        self._state = False
        self._rgb = (0, 0, 0, 0, 0)
        self._brightness = 255
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        DoHomeDevice.__init__(self, device['name'], device)

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._brightness

    @property
    def rgbww_color(self):
        """Return the color property."""
        return self._rgb

    @property
    def is_on(self):
        return self._state

    def update(self):
        """Return true if light is on."""
        data = { "cmd":25 }
        op = json.dumps(data)

        try:
            resp = self._send_cmd(self._device,'cmd=ctrl&devices={[' + self._device["sid"] + ']}&op=' + op + '}', 25)
            self._rgb = (int(resp["r"]/self.brightness), 
                    int(resp["g"]/self.brightness), 
                    int(resp["b"]/self.brightness), 
                    int(resp["w"]*255/5000),
                    int(resp["m"]*255/5000))
            self._state = (sum(self._rgb) > 0)

        except:
            _LOGGER.debug("Error when reading device state: %s", resp)

        _LOGGER.debug("Color values: %s", str(self._rgb))
        _LOGGER.debug("update: %s", str(self._state))

    @property
    def supported_features(self):
        """Return the supported features."""
        return LightEntityFeature.EFFECT | LightEntityFeature.FLASH

    @property
    def effect_list(self):
        """Return the supported effects."""
        return list(EFFECTS_DICT.keys())

    @property
    def supported_color_modes(self):
        """Return the supported color modes."""
        return [ColorMode.RGBWW]

    @property
    def color_mode(self):
        """Return the supported color modes."""
        return ColorMode.RGBWW

    @property
    def unique_id(self):
        return self._device["name"]

    def turn_on(self, **kwargs):
        """Turn the light on."""
        _LOGGER.debug("Turn on params: %s", kwargs)

        if ATTR_RGBWW_COLOR in kwargs:
            self._rgb = kwargs[ATTR_RGBWW_COLOR]

        if ATTR_BRIGHTNESS in kwargs:
            self._brightness = kwargs[ATTR_BRIGHTNESS]

        self._state = True

        if ATTR_EFFECT in kwargs:
            data = {
                    "cmd":7,
                    "index":EFFECTS_DICT[kwargs[ATTR_EFFECT]],
                    }
            op = json.dumps(data)
            self._send_cmd(self._device,'cmd=ctrl&devices={[' + self._device["sid"] + ']}&op=' + op + '}', 7)

        else:
            #empty kwargs means that turn on button has pressed without any color specification
            if len(kwargs) == 0:
                self._rgb = (0, 0, 0, 255, 0)

            data = {
                    "cmd":6,
                    "r":int(self._rgb[0] * self._brightness * 5000 / 65025),
                    "g":int(self._rgb[1] * self._brightness * 5000 / 65025),
                    "b":int(self._rgb[2] * self._brightness * 5000 / 65025),
                    "w":int(self._rgb[3] * 5000 / 255),
                    "m":int(self._rgb[4] * 5000 / 255)
                    }
            op = json.dumps(data)
            self._send_cmd(self._device,'cmd=ctrl&devices={[' + self._device["sid"] + ']}&op=' + op + '}', 6)

    def turn_off(self, **kwargs):
        """Turn the light off."""
        self._state = False
        data = {
                "cmd":6,
                "r":0,
                "g":0,
                "b":0,
                "w":0,
                "m":0}
        op = json.dumps(data)
        self._send_cmd(self._device,'cmd=ctrl&devices={[' + self._device["sid"] + ']}&op=' + op + '}', 6)

    def _send_cmd(self, device, cmd, rtn_cmd):

        try:
            self._socket.settimeout(0.5)
            self._socket.sendto(cmd.encode(), (device["sta_ip"], 6091))
            data, addr = self._socket.recvfrom(1024)
        except socket.timeout:
            return None

        if data is None:
            return None
        _LOGGER.debug("result :%s", data.decode("utf-8"))
        dic = {i.split("=")[0]:i.split("=")[1] for i in data.decode("utf-8").split("&")}
        resp = []
        if(dic["dev"][8:12] == device["sid"]):
            resp = json.loads(dic["op"])
            if resp['cmd'] != rtn_cmd:
                _LOGGER.debug("Non matching response. Expecting %s, but got %s", rtn_cmd, resp['cmd'])
                return None
            return resp
        else:
            _LOGGER.debug("Non matching response. device %s, but got %s", device["sid"], dic["dev"][8:12])
            return None
