# stdlib
import collections
import logging
import datetime
import calendar

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
        db.execute("CREATE TABLE IF NOT EXISTS {} ({});".format(cls.table_name,
            columns_definition))
        db.commit()

        # Verify that the table has exactly the right columns. The PRAGMA
        # table_info query will give us a list of tuples. For information on
        # what it gives us exaclty see
        # http://www.sqlite.org/pragma.html#pragma_table_info. Note that this
        # does not verify column contraints.
        column_info = list(db.execute("PRAGMA table_info({});".format(
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
        pre_query = "INSERT INTO {} VALUES ({});".format(self.table_name,
            ",".join(["?"] * len(self.columns)))

        # Generate the list of values we'll shove into our pre_query above
        values = []
        for i in self.columns:
            values.append(getattr(self, i.name))

        # This will execute the query after first filling in all the question
        # marks with our values. Each value will be shoved through the sqlite3
        # module's escaping function that should prevent any nasty sql
        # injection attacks.
        db.execute(pre_query, values)
        db.commit()

class Member(BaseModel):
    """Represents a single ACM@UCR member."""

    table_name = "members"
    columns = [
        Column("joined", "DATETIME", ""),
        Column("email", "TEXT", "PRIMARY KEY"),
        Column("name", "TEXT", ""),
        Column("shirt_size", "TEXT", ""),
        Column("paid_on", "DATETIME", "")
    ]

class RateLimiter(BaseModel):
    table_name = "rate_limiting"
    columns = [
        Column("minute", "INTEGER", "PRIMARY KEY"),
        Column("join_counter", "INTEGER", ""),
        Column("check_counter", "INTEGER", "")
    ]

    def insert(self, db):
        # Simply inserting a row into the rate limiting table might mess things
        # up and is never what should be done.
        raise RuntimeError("operation not supported")

    @classmethod
    def try_action(cls, db, action, max_per_minute):
        """
        Tries to record the given action in the rate limiting table.

        :param db: The SQLite database as returned by ``sqlite3.connect()``.
        :param action: The name of the action. Can be ``"check"`` or
            ``"join"``.
        :param max_per_minute: The maximum number of times the action should be
            allowed to occur in a single minute.

        :returns: ``True`` if the action should be performed, ``False``
            otherwise (the action has occurred too many times in the past
            minute).

        """

        if action == "join":
            # What will be added to the join_counter
            add_to_join_counter = 1

            # What will be added to the check_counter
            add_to_check_counter = 0

            # The column index of the counter we're modifying
            counter_index = 1
        elif action == "check":
            add_to_join_counter = 0
            add_to_check_counter = 1
            counter_index = 2
        else:
            raise ValueError("unknown action {}".format(repr(action)))

        # Form up the query that will atomically update the current minute's
        # entry in the table. This operation is often called an upsert (a
        # combination of the terms update and insert), because we will update
        # the row for the current minute if one exists, otherwise it will
        # a new row.
        upsert_pre_query = """
            INSERT OR REPLACE INTO {table_name}
                    (minute, join_counter, check_counter) VALUES (
                -- We'll fill in the minute here later by letting the sqlite3
                -- module do it. Letting the module do it helps us guard
                -- against SQL injection.
                :minute,

                -- This will add to either the current value of join_counter
                -- (which the embedded SELECT retrieves) or set the
                -- join_counter to whatever {add_to_join_counter} is.
                {add_to_join_counter} + COALESCE(
                    (SELECT join_counter FROM {table_name} WHERE
                        minute=:minute),
                    0
                ),

                -- This will do the same thing as above but to the
                -- check_counter.
                {add_to_check_counter} + COALESCE(
                    (SELECT check_counter FROM {table_name} WHERE
                        minute=:minute),
                    0
                )
            )
        """

        # Actually fill in the {bla} fields in the pre_query. We do this in two
        # steps (rather than add .format() immediately after the strings above)
        # because it looks prettier.
        upsert_pre_query = upsert_pre_query.format(
            table_name = cls.table_name,
            add_to_check_counter = add_to_check_counter,
            add_to_join_counter = add_to_join_counter
        )

        # Form up the query that will delete all the minutes we're not
        # interested in (which is any minute that has already passed). We
        # don't know that another process hasn't added a minute that's in the
        # future which is why we don't do a blanket not equal to.
        delete_pre_query = "DELETE FROM {} WHERE minute<:minute".format(
            cls.table_name)

        # Form up the query that will grab all the current minutes information
        select_pre_query = "SELECT * FROM {} WHERE minute=:minute".format(
            cls.table_name)

        # Get the current date and time and then strip out the second and
        # microsecond information. Note that even though the today() function
        # looks like it would only return a date, it does indeed also return
        # the time. Also note that the datetime object is immutable so we can't
        # just assign second and microsecond to 0.
        now = datetime.datetime.today()
        now = datetime.datetime(now.year, now.month, now.day,
            now.hour, now.minute, 0, 0, now.tzinfo)

        # Convert the time into a unix timestamp, this will be our minute
        # value.
        minute = calendar.timegm(now.utctimetuple())

        # Start a transaction and immediately lock the database to prevent
        # anyone else from making a write while we're working.
        cur = db.cursor()
        db.execute("BEGIN IMMEDIATE")

        # Execute our commands
        cur.execute(upsert_pre_query, {"minute": minute})
        cur.execute(delete_pre_query, {"minute": minute})
        cur.execute(select_pre_query, {"minute": minute})

        # Commit the transaction
        cur.execute("COMMIT")

        # This should give us a single row, the row we just upserted
        results = cur.fetchall()
        assert len(results) == 1, "Expected 1 result, got {}.".format(
            len(results))

        # Grab our one result
        results = results[0]

        log.info("Logged %r %r actions in the last minute (minute %r).",
            results[counter_index], action, minute)

        # Check the counter (which counter we're looking at is set at the top
        # of this function) to ensure there hasn't been too many requests in
        # the past minute.
        return results[counter_index] <= max_per_minute

