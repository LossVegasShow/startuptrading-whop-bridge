"""PostgreSQL rows must behave like sqlite3.Row (by name and by position)."""
from store import PgRow, PostgresResult


def test_pgrow_supports_name_and_position():
    row = PgRow({'id': 7, 'email': 'a@b.co'})
    assert row['id'] == 7 and row[0] == 7 and row[1] == 'a@b.co'
    assert dict(row) == {'id': 7, 'email': 'a@b.co'} and list(row.keys()) == ['id', 'email']


def test_count_query_shape_works_like_sqlite():
    # e.g. db.execute('SELECT COUNT(*) FROM licenses ...').fetchone()[0] (app.py admin intake)
    result = PostgresResult([{'count': 3}], 1)
    assert result.fetchone()[0] == 3
