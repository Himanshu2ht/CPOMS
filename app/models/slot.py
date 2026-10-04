from app.extensions import db


class TimeSlot(db.Model):
    __tablename__ = "time_slots"

    id = db.Column(db.Integer, primary_key=True)
    start_time = db.Column(db.DateTime, nullable=False, index=True)
    capacity = db.Column(db.Integer, nullable=False)
    booked = db.Column(db.Integer, nullable=False, default=0)

    @property
    def remaining(self):
        return max(0, self.capacity - self.booked)
