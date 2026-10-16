# Mutlak import: PyInstaller bu dosyayı paket dışı bir betik (__main__) olarak
# çalıştırır, göreli import orada çalışmaz. `python -m mychess` da buradan girer.
from mychess import main

if __name__ == "__main__":
    main()
