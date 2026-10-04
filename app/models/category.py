from app.extensions import db


class Category(db.Model):
    """Standalone category list so admins can add a category without an item."""
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(40), unique=True, nullable=False)


def all_category_names():
    """Union of the Category table and legacy MenuItem categories (sorted).

    Backfills legacy names into the table so the dropdown is always complete.
    """
    from .menu import MenuItem

    names = {c.name for c in Category.query.all()}
    names |= {r[0] for r in db.session.query(MenuItem.category).distinct().all() if r[0]}
    for name in names:
        if not Category.query.filter_by(name=name).first():
            db.session.add(Category(name=name))
    if names:
        db.session.commit()
    return sorted(names) or ["Snacks"]
