# x86 Instruction Decoding

#       MOV Ax, Bx

#    8bits          8bits
# [______|DW]  [MOD|REG|R/M]
#    6    2      2   3   3

import sys
from dataclasses import dataclass
from enum import Enum

WORD_REG_LOOKUP = ['ax', 'cx', 'dx', 'bx', 'sp', 'bp', 'si', 'di']
BYTE_REG_LOOKUP = ['al', 'cl', 'dl', 'bl', 'ah', 'ch', 'dh', 'bh']

EFFECTIVE_ADDRESS_CALCULATION_LOOKUP = [
    ['bx', 'si'],
    ['bx', 'di'],
    ['bp', 'si'],
    ['bp', 'di'],
    ['si'],
    ['di'],
    ['bp'],
    ['bx']
]

class OpType(Enum):
    REG_MEM_TO_FROM_REG = 0
    IMMEDIATE_TO_REG_MEM = 1
    IMMEDIATE_TO_REG = 2
    MEM_TO_ACCUMULATOR = 3
    ACCUMULATOR_TO_MEM = 4
    REG_MEM_TO_SEG_REG = 5
    SEG_REGTO_REG_MEM = 6
    REG_MEM = 7
    REG = 8
    SEG_REG = 9


@dataclass
class OpCode:
    value: int
    instruction: str
    size: int
    base_size_in_bytes: int = 2

    def matches(self, input):

        rshift = 8 - self.size

        return (input >> rshift) == self.value

@dataclass
class Flag:
    byte_field: int
    bitmask: bytes
    rshift: int

    def read(self, value):

        if type(value) == bytes:

            value = value[self.byte_field]

        return (value & self.bitmask) >> self.rshift

    @staticmethod
    def field(byte_field):

        return Flag(byte_field, 0b111111111, 0)



@dataclass
class InstructionSchema:
    opcode: OpCode
    flags: dict
    has_data: bool = False
    accumulator: bool = False

    def read_flag(self, flag, data):

        locator = self.flags[flag]

        return locator.read(data)

    def has_flag(self, flag):

        return flag in self.flags

    def has_displacement(self, stream, index):

        result = False

        if (self.has_flag('mod')):

            mod = self.read_flag('mod', stream[index+1])

            if (mod == 1 or mod == 2):

                result = True

            if (mod == 0):

                rm = self.read_flag('rm', stream[index+1])

                if (rm == 6):

                    result = True

        return result

    def get_displacement_in_bytes(self, stream, index):

        mod = self.read_flag('mod', stream[index+1])
        rm = self.read_flag('rm', stream[index+1])

        if (mod == 1): return 1
        if (mod == 2): return 2
        if (mod == 0 and rm == 6): return 2

        raise(f"Unknown Displacement Size: {stream[index+1]}")

    def calculate_size(self, data, index):

        size = self.opcode.base_size_in_bytes

        if self.has_displacement(data, index):

            size += self.get_displacement_in_bytes(data, index)

        if self.has_data:

            size += 1

            if self.read_flag('w', data[index]) == 1:

                size += 1

        return size

D_FLAG    = Flag(0, 0b00000010, 1)
W_FLAG1   = Flag(0, 0b00000001, 0)
W_FLAG2   = Flag(0, 0b00001000, 3)
MOD_FLAG  = Flag(1, 0b11000000, 6)
REG_FLAG1 = Flag(1, 0b00111000, 3)
REG_FLAG2 = Flag(0, 0b00000111, 0)
RM_FLAG   = Flag(1, 0b00000111, 0)
S_FLAG    = Flag(0, 0b00000010, 1)
SR_FLAG   = Flag(1, 0b00011000, 3)

INSTRUCTION_TABLE = [
    # MOV Register/memory to/from register
    InstructionSchema(
        opcode=OpCode(0b100010, "mov", 6, 2),
        flags={ 'd': D_FLAG, 'w': W_FLAG1, 'mod': MOD_FLAG, 'reg': REG_FLAG1, 'rm': RM_FLAG, 'disp_lo': Flag.field(2), 'disp_hi': Flag.field(3) }
    ),

    # MOV Immediate to register/memory
    InstructionSchema(
        opcode=OpCode(0b1100011, "mov", 7, 2),
        flags={ 'w': W_FLAG1, 'mod': MOD_FLAG, 'rm': RM_FLAG, 'disp_lo': Flag.field(2), 'disp_hi': Flag.field(2) },
        has_data=True
    ),

    # MOV Immediate to register
    InstructionSchema(
        opcode=OpCode(0b1011, "mov", 4, 2),
        flags={ 'w': W_FLAG2, 'reg': REG_FLAG2 },
        has_data=True
    ),

    # MOV Memory to accumulator
    InstructionSchema(
        opcode=OpCode(0b1010000, "mov", 7, 3),
        flags={ 'd': D_FLAG, 'w': W_FLAG1, 'addr_lo': Flag.field(1), 'addr_hi': Flag.field(2) },
        accumulator=True
    ),

    # MOV Accumulator to Memory
    InstructionSchema(
        opcode=OpCode(0b1010001, "mov", 7, 3),
        flags={ 'd': D_FLAG, 'w': W_FLAG1, 'addr_lo': Flag.field(1), 'addr_hi': Flag.field(2) },
        accumulator=True
    ),

    # MOV Register/memory to segment register
    InstructionSchema(
        opcode=OpCode(0b10001110, "mov", 8, 2),
        flags={ 'mod': MOD_FLAG, 'sr': SR_FLAG, 'rm': RM_FLAG, 'disp_lo': Flag.field(2), 'disp_hi': Flag.field(3) }
    ),

    # MOV Segment Register to register/memory
    InstructionSchema(
        opcode=OpCode(0b10001100, "mov", 8, 2),
        flags={ 'mod': MOD_FLAG, 'sr': SR_FLAG, 'rm': RM_FLAG, 'disp_lo': Flag.field(2), 'disp_hi': Flag.field(3) }
    ),

    # ADD Register/memory with regsiter to either
    InstructionSchema(
        opcode = OpCode(0b000000, "add", 6, 2),
        flags={ 'd': D_FLAG, 'w': W_FLAG1, 'mod': MOD_FLAG, 'reg': REG_FLAG1, 'rm': RM_FLAG, 'disp_lo': Flag.field(2), 'disp_hi': Flag.field(3) }
    ),

    # ADD Immediate to register/memory
    InstructionSchema(
        opcode=OpCode(0b100000, "add", 6, 2),
        flags={ 's': S_FLAG, 'w': W_FLAG1, 'mod': MOD_FLAG, 'rm': RM_FLAG, 'disp_lo': Flag.field(2), 'disp_hi': Flag.field(3) },
        has_data=True
    ),

    # ADD Immediate to accumulator
    InstructionSchema(
        opcode=OpCode(0b0000010, "add", 7, 3),
        flags={ 'w': W_FLAG1 },
        has_data=True,
        accumulator=True
    )
]

def read_binary_file(file_name):

    with open(file_name, 'rb') as file:

        return file.read()


@dataclass
class Instruction:
    schema: InstructionSchema
    data: bytes
    size: int = 2
    displacement_size_in_bytes: int = 0
    data_start_index: int = -1

    def read_flag(self, flag):

        return self.schema.read_flag(flag, self.data)

    def get_dest_register(self):

        if self.schema.accumulator:

            return 0

        if self.schema.has_flag('d') and self.read_flag('d') == 0:

            return self.read_flag('rm')

        return self.read_flag('reg')

    def get_source_register(self):

        if self.schema.has_flag('d') and self.read_flag('d') == 0:

            return self.read_flag('reg')
        
        return self.read_flag('rm')

    def read_immediate_data(self):

        if self.schema.has_flag('w') and self.read_flag('w') == 1:

            data = bytes([self.data[self.data_start_index+1], self.data[self.data_start_index]])

            return int(data.hex(), 16) & 65535

        return self.data[self.data_start_index] & 255

    def get_opperand(self, register):

        if self.read_flag('w') == 1:

            return WORD_REG_LOOKUP[register]

        else:
            
            return BYTE_REG_LOOKUP[register]

    def read_disp8(self):

        return self.data[2] & 255

    def read_disp16(self):

        data = bytes([self.data[3], self.data[2]])

        return int(data.hex(), 16) & 65535

    def get_displacement(self, mod):

        if mod == 0: return 0
        if mod == 1: return self.read_disp8()
        if mod == 2: return self.read_disp16()

    def read_address(self):

        if (self.read_flag('w') == 1):

            data = bytes([self.read_flag('addr_hi'), self.read_flag('addr_lo')])

            return int(data.hex(), 16) & 65535

        else:

            return self.read_flag('addr_lo')


    def get_asm(self):

        opcode_literal = self.schema.opcode.instruction
        opperand1 = "UNSET"
        opperand2 = "UNSET"

        if self.schema.has_flag('mod'):

            mod = self.read_flag('mod')

            if mod == 3:

                opperand1 = self.get_opperand(self.get_dest_register())

                opperand2 = self.get_opperand(self.get_source_register())

            else:

                rm = self.read_flag('rm')

                eac = EFFECTIVE_ADDRESS_CALCULATION_LOOKUP[rm].copy()
                
                disp = self.get_displacement(mod)

                if disp > 0: eac.append(str(disp))

                if (rm == 0b110):

                    opperand1 = self.get_opperand(self.get_dest_register())

                    opperand2 = "[" + str(self.read_disp16()) + "]"


                elif self.schema.has_flag('reg'):

                    d = self.read_flag('d')
                
                    if d == 1:

                        opperand1 = self.get_opperand(self.get_dest_register())

                        opperand2 = "[" + " + ".join(eac) + "]"

                    elif d == 0:

                        opperand1 = "[" + " + ".join(eac) + "]"

                        opperand2 = self.get_opperand(self.get_source_register())
                else:

                    opperand1 = "[" + " + ".join(eac) + "]"

                    if (self.schema.has_flag('w')):
                        
                        immediate_prefix = "byte"

                        if (self.read_flag('w') == 1):

                            immediate_prefix = "word"
                        
                    opperand2 = f"{immediate_prefix} {self.read_immediate_data()}" 

        else:

            # No MOD Flag
            if (self.schema.accumulator):

                if (self.read_flag('d') == 0):

                    opperand1 = self.get_opperand(0)

                    opperand2 = "[" + str(self.read_address()) + "]"

                else:

                    opperand1 = "[" + str(self.read_address()) + "]"

                    opperand2 = self.get_opperand(0)

            else:

                if (self.read_flag('d') == 0):

                    opperand1 = self.get_opperand(self.get_dest_register())

                    opperand2 = self.get_opperand(self.get_source_register())

                else:

                    opperand1 = self.get_opperand(self.get_source_register())

                    opperand2 = self.get_opperand(self.get_dest_register())


        return f"{opcode_literal} {opperand1}, {opperand2}"


def read_instruction(stream, start_index):

    displacement_size_in_bytes = 0
    data_start_index = -1

    for schema in INSTRUCTION_TABLE:

        if schema.opcode.matches(stream[start_index]):

            size = schema.calculate_size(stream, start_index)

            if (schema.has_displacement(stream, start_index)):

                displacement_size_in_bytes = schema.get_displacement_in_bytes(stream, start_index)

            if (schema.has_data):

                data_start_index = schema.opcode.base_size_in_bytes + displacement_size_in_bytes

            return Instruction(
                schema=schema,
                data=stream[start_index:start_index+size],
                size=size,
                displacement_size_in_bytes=displacement_size_in_bytes,
                data_start_index=data_start_index,
            )

    raise Exception("Unknown Instruction")


def write_asm(instructions, dest):

    with open(dest, mode='w') as file:

        file.write('bits 16\n')

        for i in instructions:

            file.write(f"{i.get_asm()}\n")


def main(file_name):

    binary_instruction_stream = read_binary_file(file_name)
    instructions = []

    i = 0
    while i < len(binary_instruction_stream):

        instruction = read_instruction(binary_instruction_stream, i)
        instructions.append(instruction)

        i = i + instruction.size

    dest = file_name + "-out-gen.asm"
    write_asm(instructions, dest)


if __name__ == "__main__":

    if len(sys.argv) > 1:

        file_path = sys.argv[1]

        main(file_path)
    else:

        print("Supply the file path.")

