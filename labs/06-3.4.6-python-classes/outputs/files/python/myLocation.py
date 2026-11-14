class Location:
    def __init__(self, name, country):
        self.name = name
        self.country = country

    def myLocation(self):
        print("Hi, my name is " + self.name + " and I live in " + self.country + ".")

# first Location object
loc1 = Location("Tomas", "Portugal")
# call the myLocation() method of that object
loc1.myLocation()

loc2 = Location("Ying", "China")
loc3 = Location("Amare", "Kenya")
loc2.myLocation()
loc3.myLocation()
your_loc = Location("Adis", "Kyrgyzstan")
your_loc.myLocation()
