#!/usr/bin/env python3
"""fids-api — flight list for the Terminal 2 board."""

import os
import time
from flask import Flask, jsonify

import pg8000.native

app = Flask(__name__)

SEED = [
    ("AF7701", "08:15", "Paris CDG", "CDG", "Air France", "A12", "Final call"),
    ("BA2633", "09:40", "London LGW", "LGW", "British Airways", "B04", "Boarding"),
    ("LH2265", "10:05", "Frankfurt FRA", "FRA", "Lufthansa", "A08", "On time"),
    ("U21842", "10:35", "London LGW", "LGW", "easyJet", "B11", "Delayed 11:10"),
    ("IB8571", "11:20", "Madrid MAD", "MAD", "Iberia", "A03", "On time"),
    ("EK076", "12:10", "Dubai DXB", "DXB", "Emirates", "C01", "Boarding"),
    ("VY1524", "13:05", "Barcelona BCN", "BCN", "Vueling", "B07", "On time"),
]


def cfg():
    return {
        "host": os.environ.get("POSTGRESQL_HOST", "fids-db"),
        "port": int(os.environ.get("POSTGRESQL_PORT", "5432")),
        "user": os.environ.get("POSTGRESQL_USER", "fids"),
        "password": os.environ.get("POSTGRESQL_PASSWORD", ""),
        "database": os.environ.get("POSTGRESQL_DATABASE", "flights"),
    }


def connect():
    c = cfg()
    return pg8000.native.Connection(
        user=c["user"],
        password=c["password"],
        host=c["host"],
        port=c["port"],
        database=c["database"],
    )


def wait_and_seed():
    attempt = 0
    while True:
        attempt += 1
        try:
            conn = connect()
            conn.run(
                """
                CREATE TABLE IF NOT EXISTS flights (
                    id SERIAL PRIMARY KEY,
                    flight TEXT NOT NULL,
                    sched_time TEXT NOT NULL,
                    destination TEXT NOT NULL,
                    airport TEXT NOT NULL,
                    airline TEXT NOT NULL,
                    gate TEXT NOT NULL,
                    status TEXT NOT NULL
                )
                """
            )
            count = conn.run("SELECT COUNT(*) FROM flights")[0][0]
            if count == 0:
                for row in SEED:
                    conn.run(
                        """
                        INSERT INTO flights
                          (flight, sched_time, destination, airport, airline, gate, status)
                        VALUES
                          (:flight, :sched_time, :destination, :airport, :airline, :gate, :status)
                        """,
                        flight=row[0],
                        sched_time=row[1],
                        destination=row[2],
                        airport=row[3],
                        airline=row[4],
                        gate=row[5],
                        status=row[6],
                    )
                count = len(SEED)
            conn.close()
            print(f"database ready after {attempt} attempt(s), rows={count}", flush=True)
            return
        except Exception as exc:
            print(f"waiting for database ({attempt}): {exc}", flush=True)
            time.sleep(2)


@app.after_request
def cors(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return resp


@app.get("/")
def root():
    return jsonify(service="fids-api", health="/health", flights="/flights")


@app.get("/health")
def health():
    try:
        conn = connect()
        conn.run("SELECT 1")
        conn.close()
        return jsonify(status="ok"), 200
    except Exception as exc:
        return jsonify(status="error", detail=str(exc)), 503


@app.get("/flights")
def flights():
    try:
        conn = connect()
        rows = conn.run(
            """
            SELECT flight, sched_time, destination, airport, airline, gate, status
            FROM flights
            ORDER BY sched_time, flight
            """
        )
        conn.close()
    except Exception as exc:
        return jsonify(error="database unavailable", detail=str(exc)), 503
    return jsonify(
        [
            {
                "flight": r[0],
                "time": r[1],
                "destination": r[2],
                "airport": r[3],
                "airline": r[4],
                "gate": r[5],
                "status": r[6],
            }
            for r in rows
        ]
    )


if __name__ == "__main__":
    import threading

    threading.Thread(target=wait_and_seed, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
