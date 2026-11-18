from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Identity, MetaData, String, Text

metadata = MetaData()


def pk(name: str) -> Column:
    return Column(name, BigInteger, Identity(), primary_key=True)


def code_pk(name: str) -> Column:
    return Column(name, String(30), primary_key=True)


def fk(name: str, target: str, nullable: bool = False) -> Column:
    return Column(name, BigInteger, ForeignKey(target), nullable=nullable)


def code_fk(name: str, target: str, nullable: bool = False) -> Column:
    return Column(name, String(30), ForeignKey(target), nullable=nullable)


def text(name: str, nullable: bool = False) -> Column:
    return Column(name, Text, nullable=nullable)


def time(name: str, nullable: bool = False) -> Column:
    return Column(name, DateTime(timezone=True), nullable=nullable)
