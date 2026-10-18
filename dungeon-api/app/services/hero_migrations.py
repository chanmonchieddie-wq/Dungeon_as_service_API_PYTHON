from sqlalchemy import Engine, inspect, text


def migrate_hero_schema(engine: Engine) -> None:
    """Add hero columns introduced after the initial database schema."""
    inspector = inspect(engine)
    if not inspector.has_table("hero"):
        return

    existing_columns = {column["name"] for column in inspector.get_columns("hero")}
    column_definitions = {
        "salle_actuelle": "VARCHAR NOT NULL DEFAULT 'entree'",
        "monstre_pv": "INTEGER",
        "or_": "INTEGER NOT NULL DEFAULT 0",
        "victoire": "BOOLEAN NOT NULL DEFAULT 0",
        "owner_id": "INTEGER",
    }

    added_or_column = "or_" not in existing_columns
    added_room_column = "salle_actuelle" not in existing_columns
    added_monster_hp_column = "monstre_pv" not in existing_columns
    with engine.begin() as connection:
        for column_name, column_type in column_definitions.items():
            if column_name not in existing_columns:
                quoted_name = engine.dialect.identifier_preparer.quote(column_name)
                connection.execute(
                    text(f"ALTER TABLE hero ADD COLUMN {quoted_name} {column_type}")
                )

        if added_or_column and "gold" in existing_columns:
            connection.execute(text("UPDATE hero SET or_ = gold"))

        if added_room_column and "salle" in existing_columns:
            connection.execute(text("UPDATE hero SET salle_actuelle = salle"))
        if added_monster_hp_column and "combat_monster_hp" in existing_columns:
            connection.execute(
                text("UPDATE hero SET monstre_pv = combat_monster_hp")
            )

        force_column = engine.dialect.identifier_preparer.quote("force")
        connection.execute(
            text(
                "UPDATE hero "
                f"SET pv = CASE WHEN pv = pv_max THEN 20 + 2 * {force_column} ELSE pv END, "
                f"pv_max = 20 + 2 * {force_column} "
                "WHERE pv_max = 20"
            )
        )

        if engine.dialect.name == "sqlite" and "salle" in existing_columns:
            connection.exec_driver_sql(
                """
                CREATE TABLE hero__migration (
                    id INTEGER NOT NULL PRIMARY KEY,
                    nom VARCHAR NOT NULL,
                    classe VARCHAR NOT NULL,
                    "force" INTEGER NOT NULL,
                    agilite INTEGER NOT NULL,
                    intelligence INTEGER NOT NULL,
                    pv INTEGER NOT NULL,
                    pv_max INTEGER NOT NULL,
                    salle_actuelle VARCHAR NOT NULL,
                    monstre_pv INTEGER,
                    or_ INTEGER NOT NULL DEFAULT 0,
                    victoire BOOLEAN NOT NULL DEFAULT 0,
                    owner_id INTEGER,
                    FOREIGN KEY(owner_id) REFERENCES player (id)
                )
                """
            )
            connection.exec_driver_sql(
                """
                INSERT INTO hero__migration (
                    id, nom, classe, "force", agilite, intelligence, pv, pv_max,
                    salle_actuelle, monstre_pv, or_, victoire, owner_id
                )
                SELECT
                    id, nom, classe, "force", agilite, intelligence, pv, pv_max,
                    salle_actuelle, monstre_pv, or_, victoire, owner_id
                FROM hero
                """
            )
            connection.exec_driver_sql("DROP TABLE hero")
            connection.exec_driver_sql(
                "ALTER TABLE hero__migration RENAME TO hero"
            )
