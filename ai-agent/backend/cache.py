import json
import os
import time
class Cache:
    def __init__(self):
        self.cache={}

    def get(self,key):
        if not self.is_contains(key):
            return None
        if self.is_expired(key):
            self.delete(key)
            return None
        return self.cache[key]["value"]

    #set value and ttl fields for cache entry
    def set(self,key,value,ttl):
        expiry=time.time()+ttl
        self.cache[key]={"value":value,"ttl":expiry}

    def is_contains(self,key):
        if key in self.cache:
            return True
        return False
    def delete(self,key):
        if self.is_contains(key):
            del self.cache[key]
        else:
            raise KeyError(f"Key '{key}' not found in cache.")

    def clear(self):
           self.cache.clear() 
    
    def invalid_multiple_keys(self, file_path):
        norm_file_path=os.path.normpath(file_path)
        prefix=f"file_path:{norm_file_path}"
        to_del=[]
        for key in self.cache:
            if key.startswith(prefix):
                to_del.append(key)
        for key in to_del:
            self.delete(key)

    
    def is_expired(self,key):
        if not self.is_contains(key):
            return False
        if self.cache[key]["ttl"] <= time.time():
            return True
        return False


    def clean_expired(self):
        to_del=[]
        for key in self.cache:
            if self.is_expired(key):
                to_del.append(key)
        for key in to_del:
            self.delete(key)

    def size(self):
        return len(self.cache)

    def keys(self):
        return list(self.cache.keys())

#so that cached items remain even if system is shut down
    def save_disk(self,file_name):
        #dumps into a JSON file with indent 
        with open(file_name,"w") as f:
            json.dump(self.cache,f,indent=4)


    def load_disk(self,file_name):
        if not os.path.exists(file_name):
            return
        with open(file_name,"r") as f:
            self.cache=json.load(f)
    #to invalidate inspect project call after write file call
    def invalidate_prefix(self,prefix):
        to_remove=[]
        for key in self.cache:
            if key.startswith(prefix):
                to_remove.append(key)
        for key in to_remove:
            del self.cache[key]


    
    