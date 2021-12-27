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
)

func mustUUID(uuids ...string) []bluetooth.UUID {
	parsed := make([]bluetooth.UUID, len(uuids))
	for i, uuid := range uuids {
		u, err := bluetooth.ParseUUID(fmt.Sprintf("0000%s-0000-1000-8000-00805f9b34fb", uuid))
		if err != nil {
			log.Panic(err)
		}
		parsed[i] = u
	}
	return parsed
}

func main() {
	withConn(printerNames, func(device *bluetooth.Device, err error) {
		if err != nil {
			log.Panic(err)
		}

		fmt.Println("Connected")

		svcs, err := device.DiscoverServices(mustUUID(idSvcPrinter))
		if err != nil {
			log.Panic(err)
		}
		svc := svcs[0]
		fmt.Println(svc)

		chrs, err := svc.DiscoverCharacteristics(mustUUID(idChrPrint, idChrNotify))
		if err != nil {
			log.Panic(err)
		}
		chrPrint := chrs[0]
		chrNotify := chrs[1]
		fmt.Println(chrPrint)
		fmt.Println(chrNotify)
	})
}
