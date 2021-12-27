package main

import (
	"fmt"
	"log"

	"tinygo.org/x/bluetooth"
)

const (
	idSvcPrinter = "ae30"
	idChrPrint   = "ae01"
	idChrNotify  = "ae02"
)

var (
	printerNames = []string{
		"GT01",
		"GB01",
		"GB02",
		"GB03",
	}
	feed10Lines = []byte{
		0x51, 0x78, 0xbd, 0x00, 0x01, 0x00, 0x19, 0x4f, 0xff, 0x51, 0x78, 0xa1, 0x00, 0x02, 0x00, 0x64, 0x00, 0xa1, 0xff,
	}
)

func check(err error) {
	if err != nil {
		log.Panic(err)
	}
}

func mustUUID(uuids ...string) []bluetooth.UUID {
	parsed := make([]bluetooth.UUID, len(uuids))
	for i, uuid := range uuids {
		u, err := bluetooth.ParseUUID(fmt.Sprintf("0000%s-0000-1000-8000-00805f9b34fb", uuid))
		check(err)
		parsed[i] = u
	}
	return parsed
}

func main() {
	withConn(printerNames, func(device *bluetooth.Device, err error) {
		check(err)

		fmt.Println("Connected")

		svcs, err := device.DiscoverServices(mustUUID(idSvcPrinter))
		check(err)
		svc := svcs[0]
		chrs, err := svc.DiscoverCharacteristics(mustUUID(idChrPrint, idChrNotify))
		check(err)
		chrPrint := chrs[0]
		// chrNotify := chrs[1] // TODO: Not supported?

		n, err := chrPrint.WriteWithoutResponse(feed10Lines)
		check(err)
		fmt.Printf("Wrote %d bytes\n", n)
	})
}
