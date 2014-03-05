# stdlib
import collections
import logging

log = logging.getLogger("rock.database")

Column = collections.namedtuple("Column", ["name", "affinity", "constraint"])
"""Definition of a column in a table."""

class BaseModel(object):
    """
    Any model classes should inherit from this class.

    Make sure to set the class attributes ``table_name`` and ``columns`` to
    appropriate values.

    """

    table_name = None
    """
    The name of the table in the sqlite database that contains object of this
    type.

    """

    columns = None
    """
    A list of Column objects describing the columns that exist in the table
    that contains objects of this type.

    """

    def __init__(self, **kwargs):
        """
        Create a new instance of the model with the values in ``kwargs``.

        Every column in the table must be given a value and no additional
        values can be provided.

        """

        # This will make sure a value was given for each column, and that no
        # unknown keys were supplied.
        if set(kwargs.keys()) != set(i.name for i in self.columns):
            raise ValueError("keys in kwargs must be same as columns")

        # This will let us access the data using the dot operator
        for k, v in kwargs.items():
            setattr(self, k, v)

        # The super keyword is special to Python and is a way to call base
        # classes' functions. If you do not understand what super does, do
        # not just blindly copy and paste it around, search the interwebs for
        # `super in python`. It's use here vs. the alternative is not
        # significant but I try to use it whenever applicable.
        super(BaseModel, self).__init__()

    @classmethod
    def create_table(cls, db):
        """
        Creates a table in the database for this model if it does not exist.
        An exception will be raised if the table already esists but does not
        have the columns we expect it to.

        Note that this does not check the constraints of the table to verify
        that they match.

        """

        # This will end up looking something like
        # "joined DATE, email TEXT PRIMARY KEY". This is a list comprehenion.
        columns_definition = ", ".join([
            "{} {} {}".format(i.name, i.affinity, i.constraint)
                for i in cls.columns])

        # Create the table if it doesn't already exist
        db.execute("CREATE TABLE IF NOT EXISTS {} ({})".format(cls.table_name,
            columns_definition))

        # Verify that the table has exactly the right columns. The PRAGMA
        # table_info query will give us a list of tuples. For information on
        # what it gives us exaclty see
        # http://www.sqlite.org/pragma.html#pragma_table_info
        column_info = list(db.execute("PRAGMA table_info({})".format(
            cls.table_name)))
        if len(column_info) != len(cls.columns):
            raise RuntimeError("table is not as expected")
        for i, j in zip(column_info, cls.columns):
            # Pull out the column's name and affinity from the data we received
            # from sqlite.
            column_name = i[1]
            column_affinity = i[2]

            # Ensure that both the affinity and the name is the same as what
            # we expect.
            if column_name != j.name or column_affinity != j.affinity:
                raise RuntimeError("table is not as expected")

    def insert(self, db):
        # This will make a string like "INSERT INTO bla VALUES (?, ?, ?)" with
        # actual question marks. The question marks will be filled in by the
        # execute call below which will ensure that SQL injection attacks can't
        # occur here.
        pre_query = "INSERT INTO {} VALUES ({})".format(self.table_name,
            ",".join(["?"] * len(self.columns)))

        # Generate the list of values we'll shove into our pre_query above
        values = []
        for i in self.columns:
            values.append(getattr(self, i.name))

        db.execute(pre_query, values)
        db.commit()

class Member(BaseModel):
    """Represents a single ACM@UCR member."""

    table_name = "members"
    columns = [
        Column("joined", "DATE", ""),
        Column("email", "TEXT", "PRIMARY KEY"),
        Column("name", "TEXT", ""),
        Column("shirt_size", "TEXT", ""),
        Column("paid_on", "DATE", "")
    ]
