import csv

class EOC_convert:
	def getMultiplier(self):
		return self.o2_mult

	def convert(self,voltage):
		o2 = voltage*self.o2_mult
		return o2


	def __init__(self,voltage,calibrate,calibrationFile="settings.csv"):
		rawOutput = voltage

		self.o2_mult = 0

		# if calibrate is "n":
		try:
			with open(calibrationFile, newline='') as csvfile:
				# Define new variable "reader" which is essentially a dictionary
				dictArray = csv.DictReader(csvfile)
				for row in dictArray:
					reader = row
			self.R_gain_set = int(reader["Gain_Set_Resistor"])
			self.o2_mult = float(reader["O2_Multiplier"])

		except FileNotFoundError:
			print("Calibration file not found. Forcing calibation.")
			calibrate = "f"
	   
		if calibrate == "f":
			print("Starting calibration:")
			self.R_gain_set = int(input("Enter instrumental amplifier gain resistor value (default is 1000Ohm):") or 1000)

		self.in_amp_gain = 100000/self.R_gain_set+1

		if calibrate != "n":
			targetO2 = float(input("Enter current O2 concentration (default is 20.95%):") or 20.95)

			self.o2_mult = targetO2/rawOutput
			self.o2_mult = round(self.o2_mult,4)

			print("Calibration complete. O2 concentration multiplier is " + str(self.o2_mult))

			tempstr = "Gain_Set_Resistor,O2_Multiplier\n" + str(self.R_gain_set) +","+ str(self.o2_mult)

			with open(calibrationFile, "w") as output:
				output.write(tempstr)



