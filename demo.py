import asyncio
from bleak import BleakScanner

TX_SERVICE_UUID = '0000af30-0000-1000-8000-00805f9b34fb'
TX_SERVICE_UUID_SHORT = 'af30'

SCAN_TIMEOUT_S = 15


async def scan():
    print('Scanning...')
    device = await BleakScanner.discover(
      service_uuids=[TX_SERVICE_UUID, TX_SERVICE_UUID_SHORT],
    )
    print(device)

asyncio.run(scan())
