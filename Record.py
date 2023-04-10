import pi_MCP342x as MCP342x
import MCP4725
import SDP800

from sshkeyboard import listen_keyboard

from gpiozero import CPUTemperature
import sys
import EOC_convert
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


def set_pump(pump_object, voltage):
	dac_voltage = (5.86 - voltage)/5.11
	dac_val = 4096 * dac_voltage/V_DD

	if voltage == 0:
		dac_val = 4095

	print("Pump voltage change: " + format(voltage, '.1f') + "V, DAC: " + str(round(dac_val,0)))
	pump_object.write(int(dac_val))


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



# def press(key):
# 	print(f"'{key}' pressed")

# def release(key):
# 	print(f"'{key}' released")

# listen_keyboard(on_press=press)



#### Setup

bus = smbus.SMBus(1)


adc1 = MCP342x.MCP342x(bus, MCP3422_ADDR, smbus)
adc2 = MCP342x.MCP342x(bus, MCP3424_ADDR, smbus)
dac = MCP4725.MCP4725(bus, MCP4725_ADDR, smbus)
# dac = MCP4725.MCP4725(address=MCP4725_ADDR, busnum=1) # Adafruit lib

typeK = thermocouples['K']		# For thermocouple temperature conversion lib
typeT = thermocouples['T']		# For thermocouple temperature conversion lib


# MCP9801 setup
bus.write_i2c_block_data(0x48, 0x01, [0b01000000])	# Set resolution to 9-bit

try:
	calibrArg = sys.argv[1]
except:
	calibrArg = "a"

# SDP800 setup
dpt = SDP800.DPT(SDP800_ADDR, bus)


# Define variables
V_DD = 3.3
last_pump_on_time = 0
last_pump_voltage = 0
pump_voltage = 0


### Electro-chemical oxygen cell (EOC) conversion class definition and calibration
adc1.set_resolution(18)
adc1.set_gain(8)
adc1.set_channel(1)			# EOC channel
adc1.write_config()

if calibrArg == "n":
	eoc = EOC_convert.EOC_convert(calibrArg)
else:
	set_pump(dac, 5)
	time.sleep(2.5)
	eoc_voltage = 0.0
	for i in range(0,5):
		time.sleep(0.35)
		eoc_voltage += adc1.read()
	eoc_voltage /= 5

	set_pump(dac, 0)

	eoc = EOC_convert.EOC_convert(calibrArg, eoc_voltage)


o2_multiplier = eoc.getMultiplier()
with open(write_file + ".cfg", "w") as output:
	output.write("o2_multiplier=" + str(format(o2_multiplier, '.5f')))



adc2.set_resolution(18)
adc2.set_gain(8)
adc2.write_config()



t_start = datetime.now()

while(True):
	#adc1_output = adc1.read()		# These give voltages in millivolts
	# TC1_voltage = adc2.read()

	if pump_voltage != last_pump_voltage:
		set_pump(dac, pump_voltage)
		last_pump_voltage = pump_voltage



	cpu_temp = CPUTemperature()

	diff_pressure = dpt.read()

	# print(adc1_output)
	# print(adc2_output)

	PCB_temp_raw = bus.read_i2c_block_data(MCP9801_ADDR, 0x00, 2)						# Get raw PCB temperature reading
	PCB_temp = int.from_bytes(bytes(PCB_temp_raw), "big", signed=True) * 2**(-8)	# Convert to temperature

	adc1.set_channel(1)				# EOC channel
	adc1.set_gain(8)
	adc1.write_config()


	TC_temps = [-99.9,-99.9,-99.9,-99.9]

	for i, temp in enumerate(TC_temps):
		adc2.set_channel(i+1, True)
		time.sleep(0.3)
		TC_voltage = adc2.read()
		try:
			if i == 1:
				TC_temps[i] = typeT.inverse_CmV(TC_voltage, Tref=PCB_temp)
			else:
				TC_temps[i] = typeK.inverse_CmV(TC_voltage, Tref=PCB_temp)
			# print(TC1_temp)
		except:
			print("TEMP CALC FAILED")

		if i == 1:
			eoc_voltage = adc1.read()		# Scale down since we used gain=8
			adc1.set_channel(2)				# Battery voltage channel
			adc1.set_gain(1)
			adc1.write_config()



	o2_conc = eoc.convert(eoc_voltage)
	batt_voltage = adc1.read()/1000*2

	# print(PCB_temp)

	timedelta = datetime.now() - t_start
	t = round(timedelta.total_seconds(), 2)


	if TC_temps[2] > 40.0:
		pump_voltage = 3
	else:
		if t-last_pump_on_time > 10:
			pump_voltage = 4
			last_pump_on_time = t
		else:
			pump_voltage = 0





	print(format(t, '.2f')
		+ ": Batt:" + str(format(batt_voltage, '.3f'))
		+ " V --- CPU: " + str(format(cpu_temp.temperature,'.1f'))
		+ " C --- PCB Temp:" + str(format(PCB_temp, '.1f'))
		+ " C --- %O2: " + str(round(o2_conc, 2))
		+ " % --- Differential Pressure: " + str(format(diff_pressure, '.3f'))
		+ " Pa --- TC1: " + str(format(TC_temps[0], '.1f'))
		+ " C - TC2: " + str(format(TC_temps[1], '.1f'))
		+ " C - TC3: " + str(format(TC_temps[2], '.1f'))
		+ " C - TC4: " + str(format(TC_temps[3], '.1f'))
		+ " C"
		)

	### Write to file ---------------------------

	tempstr = str(format(time.time(), '.2f')) + "," + str(t) + "," + str(format(pump_voltage, '.2f')) + "," + str(format(batt_voltage, '.3f')) + "," + str(format(cpu_temp.temperature,'.1f')) + "," + str(PCB_temp) + "," + str(format(o2_conc,'.3f')) + "," + str(format(diff_pressure,'.3f')) + "," + str(format(TC_temps[0],'.2f')) + "," + str(format(TC_temps[1],'.2f')) + "," + str(format(TC_temps[2],'.2f')) + "," + str(format(TC_temps[3],'.2f')) + "\n"

	with open(write_file, "a") as output:
		output.write(tempstr)

	# -------------------------------------------