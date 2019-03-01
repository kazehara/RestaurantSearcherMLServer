# -*- coding: utf-8 -*-
import psycopg2
from typing import Optional, Tuple


class DBModel:

    def __init__(self, db_name: str, host: str, user: str, password: Optional[str]):
        db = 'dbname={} host={} user={}'.format(db_name, host, user)
        if password is not None:
            db += ' password={}'.format(password)

        self.connection = psycopg2.connect(db)
        self.cursor = self.connection.cursor()

    def _execute(self, sql: str) -> bool:
        try:
            self.cursor.execute(sql)
        except psycopg2.ProgrammingError:
            return False
        return True

    def _commit(self):
        self.connection.commit()

    def select(self, sql: str) -> Optional[Tuple[str, ...]]:
        if not self._execute(sql):
            return None
        return self.cursor.fetchone()
