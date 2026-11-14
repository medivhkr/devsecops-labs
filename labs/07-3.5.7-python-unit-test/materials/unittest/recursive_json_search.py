from test_data import *
def json_search(key,input_object):
    """
    Find every key:value pair whose key equals `key`; return them as a list of dicts
    key : name of the key to look for (case sensitive)
    input_object : parsed JSON (dict or list), here the data object from test_data.py
    inner_function() does the actual recursive walk; the list is created anew per call
    returns an empty list when the key is not present
    """
    ret_val=[]
    def inner_function(key,input_object):
        if isinstance(input_object, dict): # walk through a dictionary
            for k, v in input_object.items(): # compare each key with the wanted key
                if k == key:
                    temp={k:v}
                    ret_val.append(temp)
                if isinstance(v, dict): # value is a nested dict: search it too
                    inner_function(key,v)
                elif isinstance(v, list):
                    for item in v:
                        if not isinstance(item, (str,int)): # nested dict/list: recurse
                            inner_function(key,item)
        else: # input is a list (some APIs wrap JSON objects in a list)
            for val in input_object:
                if not isinstance(val, (str,int)):
                    inner_function(key,val)
    inner_function(key,input_object)
    return ret_val
print(json_search("issueSummary",data))
