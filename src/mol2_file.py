import difflib
from typing import Iterator, List, Optional

class Mol2AtomRecord:
    def __init__(
        self,
        atom_id: int,
        atom_name: str,
        x: float,
        y: float,
        z: float,
        atom_type: str,
        subst_id: int,
        subst_name: str,
        charge: float,
        status_bit: str = ""
    ):
        self.atom_id = atom_id
        self.atom_name = atom_name
        self.x = x
        self.y = y
        self.z = z
        self.atom_type = atom_type
        self.subst_id = subst_id
        self.subst_name = subst_name
        self.charge = charge
        self.status_bit = status_bit

    @classmethod
    def from_line(cls, line: str) -> "Mol2AtomRecord":
        parts = line.split()
        # Handle cases where status_bit might be missing or merged? 
        # The sample has: 1 C -14.6614 10.3955 -0.0573 C.ar 1 **** 0.0000
        # parts: 0:id, 1:name, 2:x, 3:y, 4:z, 5:type, 6:subst_id, 7:subst_name, 8:charge, 9:status_bit(optional)
        
        # Note: The sample file lines look like fixed width but Mol2 is generally free format (whitespace separated).
        # However, to reproduce EXACTLY, we might need to be careful about formatting.
        # But the user asked for "perfectly same output", which usually implies preserving formatting if possible,
        # or at least generating a valid Mol2 that looks the same.
        # Given the "Diff" requirement, I should try to preserve the original formatting if possible,
        # or generate a standard format that matches the input.
        # Let's assume standard parsing first.
        
        atom_id = int(parts[0])
        atom_name = parts[1]
        x = float(parts[2])
        y = float(parts[3])
        z = float(parts[4])
        atom_type = parts[5]
        subst_id = int(parts[6])
        subst_name = parts[7]
        charge = float(parts[8])
        status_bit = parts[9] if len(parts) > 9 else ""
        
        return cls(atom_id, atom_name, x, y, z, atom_type, subst_id, subst_name, charge, status_bit)

    def to_line(self) -> str:
        # Format based on BarPh26NaphPhOMeTDP.mol2 analysis (refined)
        # ID: >7
        # Space: 1
        # Name: <8
        # X, Y, Z: >10.4f
        # Space: 1
        # Type: <5
        # Subst ID: >6
        # Space: 5
        # Subst Name: <4
        # Charge: >10.4f
        
        return (
            f"{self.atom_id:>7} {self.atom_name:<8}"
            f"{self.x:>10.4f}{self.y:>10.4f}{self.z:>10.4f} "
            f"{self.atom_type:<5}{self.subst_id:>6}     {self.subst_name:<4}"
            f"{self.charge:>10.4f}"
        )

class Mol2BondRecord:
    def __init__(
        self,
        bond_id: int,
        origin_atom_id: int,
        target_atom_id: int,
        bond_type: str,
        status_bit: str = ""
    ):
        self.bond_id = bond_id
        self.origin_atom_id = origin_atom_id
        self.target_atom_id = target_atom_id
        self.bond_type = bond_type
        self.status_bit = status_bit

    @classmethod
    def from_line(cls, line: str) -> "Mol2BondRecord":
        parts = line.split()
        return cls(
            int(parts[0]),
            int(parts[1]),
            int(parts[2]),
            parts[3],
            parts[4] if len(parts) > 4 else ""
        )

    def to_line(self) -> str:
        # Format based on BarPh26NaphPhOMeTDP.mol2 analysis
        # All columns >6
        return (
            f"{self.bond_id:>6}{self.origin_atom_id:>6}{self.target_atom_id:>6}{self.bond_type:>6}"
        )

class Mol2File:
    def __init__(self):
        self.sections = [] # List of (section_name, lines or objects)
        self.atoms = []
        self.bonds = []
        self.molecule_record = [] # To store @<TRIPOS>MOLECULE lines

    def load(self, content: str):
        lines = content.splitlines()
        current_section = None
        
        for line in lines:
            if line.strip() == "":
                # Empty line, maybe preserve it?
                if current_section == "ATOM":
                    # Usually atom section ends with next section tag
                    pass
                self.sections.append(("EMPTY", line))
                continue
                
            if line.startswith("@<TRIPOS>"):
                current_section = line.strip()[9:] # e.g. MOLECULE, ATOM, BOND
                self.sections.append(("SECTION_HEADER", line))
                continue

            if current_section == "MOLECULE":
                self.molecule_record.append(line)
                self.sections.append(("MOLECULE_LINE", line))
            elif current_section == "ATOM":
                atom = Mol2AtomRecord.from_line(line)
                self.atoms.append(atom)
                self.sections.append(("ATOM", atom))
            elif current_section == "BOND":
                bond = Mol2BondRecord.from_line(line)
                self.bonds.append(bond)
                self.sections.append(("BOND", bond))
            else:
                self.sections.append(("OTHER", line))

    def dump(self) -> str:
        output = []
        for type_, data in self.sections:
            if type_ == "SECTION_HEADER":
                output.append(data)
            elif type_ == "MOLECULE_LINE":
                output.append(data)
            elif type_ == "ATOM":
                output.append(data.to_line())
            elif type_ == "BOND":
                output.append(data.to_line())
            elif type_ == "OTHER":
                output.append(data)
            elif type_ == "EMPTY":
                output.append(data)
        return "\n".join(output) + "\n"

    def to_pdb(self):
        # Import here to avoid circular dependency if any
        from pdb_file import AdhocPDB, AtomRecord, ConectRecord
        
        pdb = AdhocPDB()
        
        # Convert Atoms
        for atom in self.atoms:
            # Map Mol2 atom to PDB AtomRecord
            # serial: atom_id
            # name: atom_name
            # resName: subst_name (truncated to 3 chars?)
            # chainID: 'A' (default)
            # resSeq: subst_id
            # x, y, z: x, y, z
            # element: guess from atom_type or name
            
            element = atom.atom_type.split('.')[0] # e.g. C.ar -> C
            if len(element) > 2:
                element = element[:2]
            element = element.upper()
            
            pdb_atom = AtomRecord(
                serial=atom.atom_id,
                name=atom.atom_name,
                altLoc="",
                resName=atom.subst_name[:3], # PDB resName is 3 chars
                chainID="A", # Default chain
                resSeq=atom.subst_id,
                iCode="",
                x=atom.x,
                y=atom.y,
                z=atom.z,
                occupancy=1.0,
                tempFactor=0.0,
                element=element,
                charge="" # Mol2 charge is float, PDB charge is string 2 chars (e.g. "1+", "2-"). Keep empty for now.
            )
            pdb.context.append(pdb_atom)

        # Convert Bonds to CONECT
        # PDB CONECT records list bonded atoms for each atom.
        # Mol2 lists bonds. We need to aggregate.
        connections = {}
        for bond in self.bonds:
            if bond.origin_atom_id not in connections:
                connections[bond.origin_atom_id] = []
            if bond.target_atom_id not in connections:
                connections[bond.target_atom_id] = []
            
            connections[bond.origin_atom_id].append(bond.target_atom_id)
            connections[bond.target_atom_id].append(bond.origin_atom_id) # Bonds are undirected usually

        for serial in sorted(connections.keys()):
            bonded = sorted(connections[serial])
            # PDB CONECT can handle max 4 bonds per record.
            # If more, need multiple records.
            # AdhocPDB's ConectRecord handles a list, but to_line might need adjustment if > 4?
            # Let's check ConectRecord.to_line in pdb_file.py
            # It joins all bonded. "bonded_fields = "".join(f"{b:5d}" for b in self.bonded)"
            # It doesn't seem to split into multiple lines if > 4. 
            # Standard PDB requires splitting. But for AdhocPDB, maybe it's fine?
            # Wait, standard PDB CONECT has serial in cols 7-11, then bonded atoms in 12-16, 17-21, 22-26, 27-31.
            # Max 4.
            
            # Let's split into chunks of 4
            for i in range(0, len(bonded), 4):
                chunk = bonded[i:i+4]
                pdb.context.append(ConectRecord(serial, chunk))

        return pdb

def print_diff(original: str, dumped: str):
    original_lines = original.splitlines(keepends=True)
    dumped_lines = dumped.splitlines(keepends=True)
    diff = difflib.unified_diff(
        original_lines,
        dumped_lines,
        fromfile="original",
        tofile="dumped",
        lineterm="",
    )
    print("".join(diff))

if __name__ == "__main__":
    import sys
    
    filename = "BarPh26NaphPhOMeTDP.mol2"
    if len(sys.argv) > 1:
        filename = sys.argv[1]
        
    with open(filename, "r") as f:
        content = f.read()
        
    mol2 = Mol2File()
    mol2.load(content)
    dumped = mol2.dump()
    
    print("--- Diff Check ---")
    print_diff(content, dumped)
    
    if content == dumped:
        print("\nRESULT: MATCH")
    else:
        print("\nRESULT: MISMATCH")
        
    with open("dumped.mol2", "w") as f:
        f.write(dumped)

    # Test conversion
    print("\n--- Conversion Check ---")
    pdb = mol2.to_pdb()
    pdb_content = pdb.dump()
    with open("converted.pdb", "w") as f:
        f.write(pdb_content)
    print("Converted PDB saved to converted.pdb")
