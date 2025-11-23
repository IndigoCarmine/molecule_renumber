from src.pdb_file import AdhocPDB, AtomRecord, ConectRecord

def test_find_connected_hydrogen():
    pdb = AdhocPDB()
    
    # Create Atom 1 (C)
    atom1 = AtomRecord(
        serial=1, name="C1", altLoc="", resName="ALA", chainID="A", resSeq=1, iCode="",
        x=0.0, y=0.0, z=0.0, occupancy=1.0, tempFactor=0.0, element="C", charge=""
    )
    pdb.context.append(atom1)
    
    # Create Atom 2 (H) connected to Atom 1
    atom2 = AtomRecord(
        serial=2, name="H1", altLoc="", resName="ALA", chainID="A", resSeq=1, iCode="",
        x=1.0, y=0.0, z=0.0, occupancy=1.0, tempFactor=0.0, element="H", charge=""
    )
    pdb.context.append(atom2)
    
    # Case 1: CONECT 1 2
    # Atom 1 is the source, Atom 2 is in bonded list
    pdb.context.append(ConectRecord(serial=1, bonded=[2]))
    
    hydrogens = pdb.find_connected_hydrogen(atom1)
    print(f"Case 1 (CONECT 1 2): Found {len(hydrogens)} hydrogens")
    for h in hydrogens:
        print(f"  - {h.name} (serial {h.serial})")
        
    if len(hydrogens) == 1 and hydrogens[0].serial == 2:
        print("  -> PASS")
    else:
        print("  -> FAIL")

    # Clear CONECT records for Case 2
    pdb.context = [x for x in pdb.context if not isinstance(x, ConectRecord)]
    
    # Case 2: CONECT 2 1
    # Atom 2 is the source, Atom 1 is in bonded list
    pdb.context.append(ConectRecord(serial=2, bonded=[1]))
    
    hydrogens = pdb.find_connected_hydrogen(atom1)
    print(f"Case 2 (CONECT 2 1): Found {len(hydrogens)} hydrogens")
    for h in hydrogens:
        print(f"  - {h.name} (serial {h.serial})")

    if len(hydrogens) == 1 and hydrogens[0].serial == 2:
        print("  -> PASS")
    else:
        print("  -> FAIL")

if __name__ == "__main__":
    test_find_connected_hydrogen()
