
CREATE TABLE IF NOT EXISTS "tbl_changes" (
	"number"	INTEGER NOT NULL UNIQUE,
	"project"	VARCHAR(128) NOT NULL,
	"branch"	VARCHAR(128) NOT NULL,
    "change_id"	CHAR(42) NOT NULL,
	"status"	CHAR(16) NOT NULL,
	"update_time"	INTEGER NOT NULL,
	"parent"	CHAR(42) DEFAULT NULL,
	"parent2"	CHAR(42) DEFAULT NULL,
	"author"	TEXT DEFAULT NULL,
	"author_date"	INTEGER DEFAULT NULL,
	"committer"	TEXT DEFAULT NULL,
	"committer_date"	INTEGER DEFAULT NULL,
	"data"	TEXT NOT NULL,
	PRIMARY KEY("number")
);

CREATE INDEX IF NOT EXISTS "tbl_changes_idx_project_branch_change_id" ON "tbl_changes" (
	"project",
	"branch",
	"change_id"
);
