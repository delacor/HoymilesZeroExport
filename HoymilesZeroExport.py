import requests, time
from requests.auth import HTTPBasicAuth
import os
import logging

ahoyIP = '192.168.10.57'
tasmotaIP = '192.168.10.90'

hoymilesInverterID = int(0) # number of inverter in Ahoy-Setup
hoymilesMaxWatt = int(1500) # maximum limit in watts (100%)
hoymilesMinWatt = int(hoymilesMaxWatt / 100 * 5) # minimum limit in watts
hoymilesMinOffsetInWatt = int(-100) # this is the target bandwidth the powermeter should be (powermeter watts should be between hoymilesMaxOffsetInWatt and hoymilesMinOffsetInWatt)
hoymilesMaxOffsetInWatt = int(-50) # this is the target bandwidth the powermeter should be (powermeter watts should be between hoymilesMaxOffsetInWatt and hoymilesMinOffsetInWatt)
hoymilesSetPointInWatt = int((hoymilesMinOffsetInWatt - hoymilesMaxOffsetInWatt) / 2 + hoymilesMaxOffsetInWatt) # this is the setpoint for powermeter watts
hoymilesMaxPowerDiff = int(hoymilesMaxWatt / 100 * 10) # maximum power difference between limit and output. used only for calculation to control faster.

logging.basicConfig(
    format='%(asctime)s %(levelname)-8s %(message)s',
    level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S')

def setLimit(hoymilesInverterID, Limit):
    url = f"http://{ahoyIP}/api/ctrl"
    data = f'''{{"id": {hoymilesInverterID}, "cmd": "limit_nonpersistent_absolute", "val": {Limit}}}'''
    headers = {'Content-type': 'application/json', 'Accept': 'text/plain'}
    logging.info("setting new limit to %s %s",Limit," Watt")
    requests.post(url, data=data, headers=headers)

while True:
    try:
        ParsedData = requests.get(url = f'http://{ahoyIP}/api/index').json()
        hoymilesIsReachable = bool(ParsedData["inverter"][0]["is_avail"])

        ParsedData = requests.get(url = f'http://{ahoyIP}/api/record/live').json()
        hoymilesActualPower = int(float(next(item for item in ParsedData['inverter'][0] if item['fld'] == 'P_AC')['val']))

        ParsedData = requests.get(url = f'http://{ahoyIP}/api/record/config').json()
        hoymilesActualLimit =int(float(ParsedData['inverter'][0][0]['val']) * 0.01 * hoymilesMaxWatt)

        ParsedData = requests.get(url = f'http://{tasmotaIP}/cm?cmnd=status%2010').json()
        powermeterWatts = int(ParsedData["StatusSNS"]["SML"]["curr_w"])

        newLimitSetpoint = int(hoymilesActualLimit)

        logging.info("HM reachable: %s",hoymilesIsReachable)
        logging.info("HM power: %s %s",hoymilesActualPower, " Watt")
        logging.info("powermeter: %s %s",powermeterWatts, " Watt")
        logging.info("HM Limit: %s",hoymilesActualLimit)

        if hoymilesIsReachable:
            # producing too much power: reduce limit
            if powermeterWatts < hoymilesMinOffsetInWatt:
                if abs(hoymilesActualLimit - hoymilesActualPower) > hoymilesMaxPowerDiff:
                    newLimitSetpoint = hoymilesActualPower - abs(powermeterWatts) + abs(hoymilesSetPointInWatt) # big jump to setpoint
                else:
                    newLimitSetpoint = hoymilesActualLimit - abs(powermeterWatts) + abs(hoymilesSetPointInWatt) # smaller jump to setpoint
                logging.info("Too much energy producing: reducing limit")

            # producing too little power: increase limit to maximum
            elif powermeterWatts > 0:
                newLimitSetpoint = hoymilesMaxWatt

            # producing too little power: increase limit slowly
            elif powermeterWatts > hoymilesMaxOffsetInWatt:
                if hoymilesActualLimit < hoymilesMaxWatt:
                    newLimitSetpoint = hoymilesActualLimit + abs(powermeterWatts) + abs(hoymilesSetPointInWatt)
                    logging.info("Not enough energy producing: increasing limit")
                else:
                    logging.info("Not enough energy producing: limit already at maximum")

            # check for upper and lower limits
            if newLimitSetpoint > hoymilesMaxWatt:
                newLimitSetpoint = hoymilesMaxWatt
            if newLimitSetpoint < hoymilesMinWatt:
                newLimitSetpoint = hoymilesMinWatt

            # set new limit to inverter
            if hoymilesActualLimit != newLimitSetpoint:
                setLimit(hoymilesInverterID, newLimitSetpoint)

        time.sleep(10)

    except TypeError as e:
        logging.error(e)
        time.sleep(10)
