import json
import os
import time
import threading
class Cache:
    def __init__(self):
        self.cache={}
        self.lock=threading.RLock()

    def get(self,key):
        with self.lock:
            if not self.is_contains(key):
                return None
            if self.is_expired(key):
                self.delete(key)
                return None
            return self.cache[key]["value"]

    #set value and ttl fields for cache entry
    def set(self,key,value,ttl):
        with self.lock:
            expiry=time.time()+ttl
            self.cache[key]={"value":value,"ttl":expiry}

    def is_contains(self,key):
        if key in self.cache:
            return True
        return False
    def delete(self,key):
        with self.lock:
            # if self.is_contains(key):
            #     del self.cache[key]
            # else:
            #     raise KeyError(f"Key '{key}' not found in cache.")
            self.cache.pop(key,None)

    def clear(self):
           self.cache.clear() 
    
    def invalid_multiple_keys(self, file_path):
        with self.lock:
            norm_file_path=os.path.normpath(file_path)

            prefix=f"file_path:{norm_file_path}|"
            to_del=[key for key in self.cache if key.startswith(prefix)]
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
        with self.lock:
            to_del=[]
            for key in self.cache:
                if self.is_expired(key):
                    to_del.append(key)
            for key in to_del:
                self.delete(key)

    def size(self):
        with self.lock:
            return len(self.cache)

    def keys(self):
        with self.lock:
            return list(self.cache.keys())

#so that cached items remain even if system is shut down
    def save_disk(self,file_name):
        with self.lock:
        #dumps into a JSON file with indent 
            with open(file_name,"w") as f:
                json.dump(self.cache,f,indent=4)


    def load_disk(self,file_name):
        with self.lock:
            if not os.path.exists(file_name):
                return
            try:
                with open(file_name,"r") as f:
                    data=json.load(f)
                if isinstance(data,dict):
                    self.cache=data

            except (json.JSONDecodeError,OSError) as e:
                print(f"Cache file unreadable, starting empty: {e}")
                self.cache={}


    #to invalidate inspect project call after write file call
    def invalidate_prefix(self,prefix):
        with self.lock:
            to_remove=[]
            for key in self.cache:
                if key.startswith(prefix):
                    to_remove.append(key)
            for key in to_remove:
                del self.cache[key]


    
    