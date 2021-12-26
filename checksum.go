package main

import "github.com/sigurn/crc8"

var crcTable *crc8.Table

func init() {
	crcTable = crc8.MakeTable(crc8.CRC8)
}

func checksum(data []byte) uint8 {
	return crc8.Checksum(data, crcTable)
}
