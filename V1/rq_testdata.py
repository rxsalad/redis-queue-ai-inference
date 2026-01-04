
string_10  = '0123456789'
string_20  = '01234567899876543210' 
string_50  = '0123456789' * 5
string_100 = '0123456789' * 10

string_1000 = string_100 * 10

list_10_100 = [string_100 for i in range(10)]
list_20_50  = [string_50 for i in range(20)]

list_50_20 = [string_20 for i in range(50)]
