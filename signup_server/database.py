class Member(object):
    table_name = "members"
    columns = [
        ("joined", "DATE"),
        ("email", "TEXT"),
        ("name", "TEXT"),
        ("shirt_size", "TEXT"),
        ("paid_on", "DATE")
    ]

    def __init__(self, **kwargs):
        # This will make sure a value was given for each column, and that no
        # unknown keys were supplied.
        if set(kwargs.keys()) != set(i[0] for i in self.columns):
            raise ValueError("keys in kwargs must be same as columns")

        # This will let us access the data using the dot operator
        for k, v in kwargs.items():
            setattr(self, k, v)

    @classmethod
    def create_table(cls, db):
        # This will end up looking something like "joined DATE, email TEXT"
        columns_definition = ", ".join(["{} {}".format(i[0], i[1])
            for i in cls.columns])

        cur = db.cursor()

        # Create the table if it doesn't already exist
        cur.execute("CREATE TABLE IF NOT EXISTS {} ({})".format(cls.table_name,
            columns_definition))

        # Verify that the table has exactly the right columns. The PRAGMA
        # table_info query will give us a list of tuples. For information on
        # what it gives us exaclty see
        # http://www.sqlite.org/pragma.html#pragma_table_info
        cur.execute("PRAGMA table_info({})".format(cls.table_name))
        column_info = cur.fetchall()
        if len(column_info) != len(cls.columns):
            raise RuntimeError("table is not as expected")
        for i, j in zip(column_info, cls.columns):
            column_name = i[1]
            column_type = i[2]

            if column_name != j[0] or column_type != j[1]:
                raise RuntimeError("table is not as expected")

def initialize_database():
    db.execute("""CREATE TABLE IF NOT EXISTS members (DATE joined, TEXT email,
        TEXT name, TEXT shirt_size, DATE paid_on)""")
