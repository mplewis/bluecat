package main

import (
	"fmt"
	"log"
	"math"

	"tinygo.org/x/bluetooth"
)

type Cmd = []byte

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
	cmdFeedPaper = []byte{0xa1}
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

func b(b ...byte) []byte {
	return b
}

func cat(arr ...[]byte) []byte {
	var result []byte
	for _, a := range arr {
		result = append(result, a...)
	}
	return result
}

func build(cmd []byte, data []byte) Cmd {
	return cat(b(0x51, 0x78), cmd, b(0x00, byte(len(data)), 0x00), data, b(byte(checksum(data)), 0xff))
}

func feed(lines int) Cmd {
	fmt.Println(lines)
	cmds := Cmd{}
	for lines > 0 {
		toPrint := math.Min(float64(lines), 255)
		cmds = append(cmds, build(cmdFeedPaper, b(byte(toPrint)))...)
		lines -= int(toPrint)
		fmt.Println(toPrint)
		fmt.Println(lines)
	}
	return cmds
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

		n, err := chrPrint.WriteWithoutResponse(feed(100))
		check(err)
		fmt.Printf("Wrote %d bytes\n", n)
		n, err = chrPrint.WriteWithoutResponse(feed(100))
		check(err)
		fmt.Printf("Wrote %d bytes\n", n)
		n, err = chrPrint.WriteWithoutResponse(feed(100))
		check(err)
		fmt.Printf("Wrote %d bytes\n", n)
		n, err = chrPrint.WriteWithoutResponse(feed(100))
		check(err)
		fmt.Printf("Wrote %d bytes\n", n)
	})
}
