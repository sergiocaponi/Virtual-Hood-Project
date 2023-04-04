import pi_MCP342x as MCP342x
import MCP4725
import SDP800

import sys
import EOC_convert as EOC_convert
from datetime import datetime

import smbus2 as smbus
import time
#import Adafruit_MCP4725 as MCP4725
from thermocouples_reference import thermocouples

SDP800_ADDR = 0x25

MCP3422_ADDR = 0x68		# 2-channel ADC address (O2 sensor on ch1 and battery voltage on ch2)
MCP3424_ADDR = 0x6b		# 4-channel ADC address (Thermocouples on all channels)

MCP9801_ADDR = 0x48		# On-board temperature monitor chip address (for TC cold junction)

MCP4725_ADDR = 0x67		# DAC address (for motor voltage control)


#### Setup

bus = smbus.SMBus(1)


adc1 = MCP342x.MCP342x(bus, MCP3422_ADDR, smbus)
adc2 = MCP342x.MCP342x(bus, MCP3424_ADDR, smbus)
dac = MCP4725.MCP4725(bus, MCP4725_ADDR, smbus)
# dac = MCP4725.MCP4725(address=MCP4725_ADDR, busnum=1) # Adafruit lib

typeK = thermocouples['K']		# For thermocouple temperature conversion lib

# MCP9801 setup
bus.write_i2c_block_data(0x48, 0x01, [0b01000000])	# Set resolution to 9-bit

calibrArg = sys.argv[1]

# SDP800 setup
dpt = SDP800.DPT(SDP800_ADDR, bus)


#### Sequence

# dac.write(1000)

# Electro-chemical oxygen cell conversion class
adc1.set_resolution(18)
adc1.set_channel(1)			# EOC channel
adc1.write_config()
time.sleep(0.4)
adc1_output = adc1.read()

eoc = EOC_convert.EOC_convert(adc1_output, calibrArg)

adc2.set_resolution(18)
adc2.set_channel(1)
adc2.set_gain(8)
adc2.write_config()

time.sleep(0.5)


t_start = datetime.now()

while(True):
	#adc1_output = adc1.read()		# These give voltages in millivolts
	TC1_voltage = adc2.read()


	diff_pressure = dpt.read()

	# print(adc1_output)
	# print(adc2_output)

	PCB_temp_raw = bus.read_i2c_block_data(0x48, 0x00, 2)						# Get raw PCB temperature reading
	PCB_temp = int.from_bytes(bytes(PCB_temp_raw), "big", signed=True) * 2**(-8)	# Convert to temperature

	adc1.set_channel(1, True)				# EOC channel
	time.sleep(0.4)
	eoc_voltage = adc1.read()
	o2_conc = eoc.convert(eoc_voltage)

	adc1.set_channel(2, True)				# Battery voltage channel
	time.sleep(0.4)
	batt_voltage = adc1.read()/1000*2

	# print(PCB_temp)

	try:
		TC1_temp = typeK.inverse_CmV(TC1_voltage, Tref=PCB_temp)
		# print(TC1_temp)
	except:
		print("TEMP CALC FAILED")
	# time.sleep(0.5)


	timedelta = datetime.now() - t_start
	t = round(timedelta.total_seconds(), 2)


	print(format(t, '.2f')
		+ ": PCB Temp: " + str(PCB_temp)
		+ " C --- TC Temp: " + str(round(TC1_temp,1))
		+ " C --- %O2: " + str(round(o2_conc,4))
		+ " % --- Differential Pressure: " + str(round(diff_pressure,3))
		+ " Pa --- Battery voltage:" + str(round(batt_voltage, 3))
		+ " V"
		)
