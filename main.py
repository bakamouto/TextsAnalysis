from functions import *

data_file = "messages_studsovet_4.json"
key_file = "key.txt"

directory = "results-4"
delta = 10 * 60
tokens = 6000

summarise_by_month(data_file, delta, tokens, directory)
summarise_months(directory, "summary_by_months-4.json", get_key(key_file))
