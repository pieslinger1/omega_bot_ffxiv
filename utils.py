import random
import string

def generate_random_id_string(N = 10):
	return ''.join(random.choices(string.ascii_uppercase + string.digits, k=N))

def order_strings(str1, str2):
	if str1 < str2:
		return (str1, str2)
	return (str2, str1)