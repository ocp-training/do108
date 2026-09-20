#!/usr/bin/env python3
"""fids-admin — airport managers add, update and remove flights."""

import os
import re
import time
from flask import Flask, flash, redirect, render_template, request, url_for

import pg8000.native

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "fids-admin-training")

STATUSES = (
    "On time",
    "Boarding",
    "Final call",
    "Delayed",
    "Gate closed",
    "Departed",
    "Cancelled",
)
FIELDS = ("flight", "sched_time", "destination", "airport", "airline", "gate", "status")
TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


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


def ensure_schema():
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
            conn.close()
            print(f"database ready after {attempt} attempt(s)", flush=True)
            return
        except Exception as exc:
            print(f"waiting for database ({attempt}): {exc}", flush=True)
            time.sleep(2)


def row_to_flight(r):
    return {
        "id": r[0],
        "flight": r[1],
        "sched_time": r[2],
        "destination": r[3],
        "airport": r[4],
        "airline": r[5],
        "gate": r[6],
        "status": r[7],
    }


def list_flights():
    conn = connect()
    rows = conn.run(
        """
        SELECT id, flight, sched_time, destination, airport, airline, gate, status
        FROM flights
        ORDER BY sched_time, flight
        """
    )
    conn.close()
    return [row_to_flight(r) for r in rows]


def get_flight(flight_id):
    conn = connect()
    rows = conn.run(
        """
        SELECT id, flight, sched_time, destination, airport, airline, gate, status
        FROM flights WHERE id = :id
        """,
        id=flight_id,
    )
    conn.close()
    return row_to_flight(rows[0]) if rows else None


def form_values():
    values = {name: (request.form.get(name) or "").strip() for name in FIELDS}
    values["flight"] = values["flight"].upper()
    values["airport"] = values["airport"].upper()
    values["gate"] = values["gate"].upper()
    return values


def validate(values):
    missing = [name for name in FIELDS if not values[name]]
    if missing:
        return "Fill every field before saving."
    if not TIME_RE.match(values["sched_time"]):
        return "Scheduled time must be HH:MM (24-hour)."
    if values["status"] not in STATUSES:
        return "Choose a status from the list."
    if len(values["flight"]) > 8:
        return "Flight number is too long."
    return None


@app.template_global()
def klass(status):
    s = (status or "").lower()
    if "final" in s:
        return "final"
    if "board" in s:
        return "board"
    if "delay" in s or "cancel" in s or "closed" in s or "depart" in s:
        return "delay"
    return "on"


@app.get("/health")
def health():
    try:
        conn = connect()
        conn.run("SELECT 1")
        conn.close()
        return {"status": "ok"}, 200
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}, 503


@app.get("/")
def index():
    edit_id = request.args.get("edit", type=int)
    editing = get_flight(edit_id) if edit_id else None
    try:
        flights = list_flights()
        db_ok = True
        error = None
    except Exception as exc:
        flights = []
        db_ok = False
        error = str(exc)
    return render_template(
        "index.html",
        flights=flights,
        editing=editing,
        statuses=STATUSES,
        db_ok=db_ok,
        error=error,
    )


@app.post("/flights")
def create_flight():
    values = form_values()
    problem = validate(values)
    if problem:
        flash(problem, "err")
        return redirect(url_for("index"))
    try:
        conn = connect()
        conn.run(
            """
            INSERT INTO flights
              (flight, sched_time, destination, airport, airline, gate, status)
            VALUES
              (:flight, :sched_time, :destination, :airport, :airline, :gate, :status)
            """,
            **values,
        )
        conn.close()
        flash(f"Added {values['flight']} to {values['destination']}.", "ok")
    except Exception as exc:
        flash(f"Could not add the flight: {exc}", "err")
    return redirect(url_for("index"))


@app.post("/flights/<int:flight_id>/update")
def update_flight(flight_id):
    if not get_flight(flight_id):
        flash("That flight is no longer in the database.", "err")
        return redirect(url_for("index"))
    values = form_values()
    problem = validate(values)
    if problem:
        flash(problem, "err")
        return redirect(url_for("index", edit=flight_id))
    try:
        conn = connect()
        conn.run(
            """
            UPDATE flights
            SET flight = :flight,
                sched_time = :sched_time,
                destination = :destination,
                airport = :airport,
                airline = :airline,
                gate = :gate,
                status = :status
            WHERE id = :id
            """,
            id=flight_id,
            **values,
        )
        conn.close()
        flash(f"Updated {values['flight']}.", "ok")
    except Exception as exc:
        flash(f"Could not update the flight: {exc}", "err")
    return redirect(url_for("index"))


@app.post("/flights/<int:flight_id>/delete")
def delete_flight(flight_id):
    current = get_flight(flight_id)
    if not current:
        flash("That flight is no longer in the database.", "err")
        return redirect(url_for("index"))
    try:
        conn = connect()
        conn.run("DELETE FROM flights WHERE id = :id", id=flight_id)
        conn.close()
        flash(f"Removed {current['flight']}.", "ok")
    except Exception as exc:
        flash(f"Could not remove the flight: {exc}", "err")
    return redirect(url_for("index"))


if __name__ == "__main__":
    import threading

    threading.Thread(target=ensure_schema, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
