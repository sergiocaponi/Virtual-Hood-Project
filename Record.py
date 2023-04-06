import pi_MCP342x as MCP342x
import MCP4725
import SDP800

from gpiozero import CPUTemperature
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




### File setup ----------------------------------
try:
	write_file = sys.argv[2] + ".csv"
except:
	print('Enter filename to log (without including extension):')
	write_file = input() + ".csv"

# Wipe file
with open(write_file, "w") as output:
	output.write("")

### ---------------------------------------------





#### Setup

bus = smbus.SMBus(1)


adc1 = MCP342x.MCP342x(bus, MCP3422_ADDR, smbus)
adc2 = MCP342x.MCP342x(bus, MCP3424_ADDR, smbus)
dac = MCP4725.MCP4725(bus, MCP4725_ADDR, smbus)
# dac = MCP4725.MCP4725(address=MCP4725_ADDR, busnum=1) # Adafruit lib

typeK = thermocouples['K']		# For thermocouple temperature conversion lib

# MCP9801 setup
bus.write_i2c_block_data(0x48, 0x01, [0b01000000])	# Set resolution to 9-bit

try:
	calibrArg = sys.argv[1]
except:
	calibrArg = "a"

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
	# TC1_voltage = adc2.read()

	cpu_temp = CPUTemperature()

	diff_pressure = dpt.read()

	# print(adc1_output)
	# print(adc2_output)

	PCB_temp_raw = bus.read_i2c_block_data(MCP9801_ADDR, 0x00, 2)						# Get raw PCB temperature reading
	PCB_temp = int.from_bytes(bytes(PCB_temp_raw), "big", signed=True) * 2**(-8)	# Convert to temperature

	adc1.set_channel(1, True)				# EOC channel

	TC_temps = [-99.9,-99.9,-99.9,-99.9]

	i = 1
	for temp in TC_temps:
		adc2.set_channel(i, True)
		time.sleep(0.3)
		TC_voltage = adc2.read()
		try:
			temp = typeK.inverse_CmV(TC_voltage, Tref=PCB_temp)
			# print(TC1_temp)
		except:
			print("TEMP CALC FAILED")

		if i == 2:
			eoc_voltage = adc1.read()
			adc1.set_channel(2, True)				# Battery voltage channel

		i += 1


	o2_conc = eoc.convert(eoc_voltage)
	batt_voltage = adc1.read()/1000*2

	# print(PCB_temp)





	timedelta = datetime.now() - t_start
	t = round(timedelta.total_seconds(), 2)


	print(format(t, '.2f')
		+ ": Batt:" + str(round(batt_voltage, 3))
		+ " V --- CPU: " + cpu_temp
		+ " C --- PCB Temp:" + str(PCB_temp)
		+ " C --- %O2: " + str(round(o2_conc,4))
		+ " % --- Differential Pressure: " + str(round(diff_pressure,3))
		+ " Pa --- TC1: " + str(round(TC_temps[1],2))
		+ " C - TC2: " + str(round(TC_temps[2],2))
		+ " C - TC3: " + str(round(TC_temps[3],2))
		+ " C - TC4: " + str(round(TC_temps[4],2))
		+ " C"
		)

	### Write to file ---------------------------

	tempstr = str(round(time.time(), 2)) + "," + str(t) + "," + str(round(batt_voltage, 3)) + "," + str(cpu_temp.Temperature) + "," + str(PCB_temp) + "," + str(round(o2_conc,4)) + "," + str(round(diff_pressure,3)) + "," + str(round(TC_temps[1],2)) + "," + str(round(TC_temps[2],2)) + "," + str(round(TC_temps[3],2)) + "," + str(round(TC_temps[3],2)) + "\n"
    with open(write_file, "a") as output:
		output.write(tempstr)

	# -------------------------------------------