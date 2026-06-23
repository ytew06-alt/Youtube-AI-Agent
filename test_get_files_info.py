from functions.get_files_info import get_files_info
test1=get_files_info("calculator",".")
print(f"Test 1: {test1}")
test2=get_files_info("calculator","pkg")
print(f"Test 2: {test2}")
test3=get_files_info("calculator","/bin")
print(f"Test 3: {test3}")
test4=get_files_info("calculator","../")
print(f"Test 4: {test4}")