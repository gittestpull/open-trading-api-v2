import urllib.request
import ssl
import zipfile
import os
import pandas as pd

class StockMaster:
    def __init__(self, base_dir=None):
        if base_dir is None:
            self.base_dir = os.getcwd()
        else:
            self.base_dir = base_dir
            
        self.kospi_master = None
        self.kosdaq_master = None
        
        # SSL Context
        ssl._create_default_https_context = ssl._create_unverified_context

    def _download_and_extract(self, market):
        url = f"https://new.real.download.dws.co.kr/common/master/{market}_code.mst.zip"
        zip_file = os.path.join(self.base_dir, f"{market}_code.zip")
        mst_file = os.path.join(self.base_dir, f"{market}_code.mst")
        
        if not os.path.exists(mst_file):
            print(f"[{market}] Master file not found. Downloading...")
            try:
                urllib.request.urlretrieve(url, zip_file)
                with zipfile.ZipFile(zip_file) as z:
                    z.extractall(self.base_dir)
                if os.path.exists(zip_file):
                    os.remove(zip_file)
                print(f"[{market}] Download Complete.")
            except Exception as e:
                print(f"[{market}] Download Failed: {e}")
                return False
        return True

    def _parse_master(self, market):
        mst_file = os.path.join(self.base_dir, f"{market}_code.mst")
        if not os.path.exists(mst_file):
            return {}

        code_map = {}
        # Part 1 format is common:
        # 0-9: Short Code (Main)
        # 9-21: Standard Code
        # 21-...: Name
        
        try:
            with open(mst_file, mode="r", encoding="cp949") as f:
                for row in f:
                    # Specific lengths based on KOSPI/KOSDAQ logic, but simpler approach:
                    # KOSPI: len(row) - 228 is Part 1
                    # KOSDAQ: len(row) - 222 is Part 1
                    cutoff = 228 if market == 'kospi' else 222
                    part1 = row[0:len(row) - cutoff]
                    
                    if len(part1) > 21:
                        code = part1[0:9].rstrip()
                        # name = part1[21:].strip() 
                        # Name sometimes has trailing spaces or garbage?
                        # Let's trust the slice.
                        name = part1[21:].strip()
                        
                        code_map[name] = code
                        
        except Exception as e:
            print(f"[{market}] Parse Error: {e}")
            
        return code_map

    def get_code(self, name):
        # Check KOSPI first
        if self.kospi_master is None:
            if self._download_and_extract('kospi'):
                self.kospi_master = self._parse_master('kospi')
            else:
                self.kospi_master = {}
        
        if name in self.kospi_master:
            return self.kospi_master[name]
            
        # Check KOSDAQ
        if self.kosdaq_master is None:
            if self._download_and_extract('kosdaq'):
                self.kosdaq_master = self._parse_master('kosdaq')
            else:
                self.kosdaq_master = {}
                
        if name in self.kosdaq_master:
            return self.kosdaq_master[name]
            
        return None

    def get_name(self, code):
        # Check KOSPI first
        if self.kospi_master is None:
            if self._download_and_extract('kospi'):
                self.kospi_master = self._parse_master('kospi')
            else:
                self.kospi_master = {}
        
        # Reverse search in KOSPI
        for name, cd in self.kospi_master.items():
            if cd == code:
                return name
                
        # Check KOSDAQ
        if self.kosdaq_master is None:
            if self._download_and_extract('kosdaq'):
                self.kosdaq_master = self._parse_master('kosdaq')
            else:
                self.kosdaq_master = {}
                
        # Reverse search in KOSDAQ
        for name, cd in self.kosdaq_master.items():
            if cd == code:
                return name
                
        return None

def get_stock_code(name):
    """
    Helper function for direct usage without instantiating StockMaster
    """
    master = StockMaster()
    return master.get_code(name)

