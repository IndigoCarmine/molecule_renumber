import re
from typing import Iterator


class AtomRecord:
    """
    PDB ATOMレコード(固定カラム形式)を読み書きするクラス。
    """

    def __init__(
        self,
        serial: int,
        name: str,
        altLoc: str,
        resName: str,
        chainID: str,
        resSeq: int,
        iCode: str,
        x: float,
        y: float,
        z: float,
        occupancy: float,
        tempFactor: float,
        element: str,
        charge: str,
    ):
        self.serial = serial
        self.name = name
        self.altLoc = altLoc
        self.resName = resName
        self.chainID = chainID
        self.resSeq = resSeq
        self.iCode = iCode
        self.x = x
        self.y = y
        self.z = z
        self.occupancy = occupancy
        self.tempFactor = tempFactor
        self.element = element
        self.charge = charge

    @classmethod
    def from_line(cls, line: str) -> "AtomRecord":
        """
        1行のPDB ATOMレコード文字列からPDBAtomRecordを生成。
        列位置はPDB仕様に準拠。
        """
        return cls(
            serial=int(line[6:11].strip()),
            name=line[12:16].strip(),
            altLoc=line[16].strip() or "",
            resName=line[17:20].strip(),
            chainID=line[21].strip() or "",
            resSeq=int(line[22:26].strip()),
            iCode=line[26].strip() or "",
            x=float(line[30:38].strip()),
            y=float(line[38:46].strip()),
            z=float(line[46:54].strip()),
            occupancy=float(line[54:60].strip() or 0.0),
            tempFactor=float(line[60:66].strip() or 0.0),
            element=line[76:78].strip(),
            charge=line[78:80].strip(),
        )

    def to_line(self) -> str:
        """
        PDB仕様に沿って1行文字列に整形。
        """
        return (
            f"ATOM  "
            f"{self.serial:5d} "
            f"{self.name:<4s}"
            f"{self.altLoc:1s}"
            f"{self.resName:>3s} "
            f"{self.chainID:1s}"
            f"{self.resSeq:4d}"
            f"{self.iCode:1s}   "
            f"{self.x:8.3f}"
            f"{self.y:8.3f}"
            f"{self.z:8.3f}"
            f"{self.occupancy:6.2f}"
            f"{self.tempFactor:6.2f}          "
            f"{self.element:>2s}"
            f"{self.charge:>2s}"
        )

    def __repr__(self) -> str:
        return (
            f"PDBAtomRecord(serial={self.serial}, name='{self.name}', resName='{self.resName}', "
            f"chainID='{self.chainID}', resSeq={self.resSeq}, x={self.x}, y={self.y}, z={self.z}, "
            f"element='{self.element}', charge='{self.charge}')"
        )


class ConectRecord:
    """
    PDB CONECTレコードを読み書きするクラス。
    例:
    CONECT    1    2    3    4
    """

    def __init__(self, serial: int, bonded: list[int]):
        """
        Parameters
        ----------
        serial : int
            このレコードの中心となる原子番号
        bonded : List[int]
            接続先の原子番号リスト（最大4つ）
        """
        self.serial = serial
        self.bonded = bonded

    @classmethod
    def from_line(cls, line: str) -> "ConectRecord":
        """
        1行のCONECTレコードをパースしてインスタンス化する。
        """
        serial = int(line[6:11].strip())
        bonded = []
        # 最大4つの接続先カラムを順次読み取る
        for start, end in [(11, 16), (16, 21), (21, 26), (26, 31)]:
            val = line[start:end].strip()
            if val:
                bonded.append(int(val))
        return cls(serial, bonded)

    def to_line(self) -> str:
        """
        CONECTレコードをPDBフォーマット文字列として整形。
        """
        bonded_fields = "".join(f"{b:5d}" for b in self.bonded)
        # 4つ未満ならスペースで埋める
        bonded_fields = bonded_fields.ljust(20)
        return f"CONECT{self.serial:5d}{bonded_fields}"

    def __repr__(self) -> str:
        return f"PDBConectRecord(serial={self.serial}, bonded={self.bonded})"


class AdhocPDB:
    """
    簡易PDBパーサー/ライター。
    ATOMレコードのみを扱い、他のレコードはStrとして管理する。
    """

    def __init__(self):
        self.context: list[str | AtomRecord | ConectRecord] = []

    def load(self, pdb_text: str):
        """
        PDBテキストを読み込み、ATOMレコードをパースする。
        """
        self.context.clear()
        for line in pdb_text.splitlines():
            if line.startswith("ATOM"):
                try:
                    atom = AtomRecord.from_line(line)
                    self.context.append(atom)
                except ValueError:
                    self.context.append(line)  # フォーマットエラーはそのまま保存
            elif line.startswith("CONECT"):
                try:
                    conect = ConectRecord.from_line(line)
                    self.context.append(conect)
                except ValueError:
                    self.context.append(line)  # フォーマットエラーはそのまま保存
            else:
                self.context.append(line)

    def load_file(self, filepath: str):
        """
        ファイルからPDBテキストを読み込む。
        """
        with open(filepath, "r") as f:
            self.load(f.read())

    def dump(self) -> str:
        """
        現在の内容をPDBフォーマットのテキストに変換する。
        """
        lines = []
        for entry in self.context:
            if isinstance(entry, AtomRecord):
                lines.append(entry.to_line())
            elif isinstance(entry, ConectRecord):
                lines.append(entry.to_line())
            else:
                lines.append(entry)
        return "\n".join(lines) + "\n"

    def get_atoms(self) -> Iterator[AtomRecord]:
        """
        現在のATOMレコードをイテレートする。
        """
        for entry in self.context:
            if isinstance(entry, AtomRecord):
                yield entry

    def get_conects(self) -> Iterator[ConectRecord]:
        """
        現在のCONECTレコードをイテレートする。
        """
        for entry in self.context:
            if isinstance(entry, ConectRecord):
                yield entry

    def replace_atom(self, old_atom: AtomRecord, new_atom: AtomRecord):
        """
        指定した古いATOMレコードを新しいATOMレコードで置換する。
        """
        for i, entry in enumerate(self.context):
            if entry is old_atom:
                self.context[i] = new_atom
                return
        raise ValueError("Old atom record not found in context.")

    def find_connected_hydrogen(self, atom: AtomRecord) -> list[AtomRecord]:
        """
        指定した原子に結合している水素原子を探す。
        """
        connected_atoms = []
        for conect in self.get_conects():
            if atom.serial in conect.bonded:
                connected_atoms.extend(conect.bonded)
        hydrogens = []
        for serial in connected_atoms:
            for a in self.get_atoms():
                if a.serial == serial and "H" in a.name:
                    hydrogens.append(a)
        return hydrogens


def print_diff(original: str, dumped: str):
    """
    2つのテキストの差分を行単位で表示する。
    """
    import difflib

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
    # test
    pdbfile = AdhocPDB()
    text = ""
    with open("A.pdb", "r") as f:
        text = f.read()
    pdbfile.load(text)

    # compare text and dump
    dumped = pdbfile.dump()
    print_diff(text, dumped)
    # save
    with open("A_out.pdb", "w") as f:
        f.write(dumped)
