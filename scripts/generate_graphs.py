#!/usr/bin/env python3
"""
Generate Schema Graph and Relational Entity Graph for Assignment 2 (Question 1).
Outputs:
  - reports/schema_graph.dot
  - reports/schema_graph.png
  - reports/relational_entity_graph.dot
  - reports/relational_entity_graph.png
"""

import os
import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt

os.makedirs("reports", exist_ok=True)

# ==========================================
# 1. Schema Graph Generation
# ==========================================
schema_dot = """digraph SchemaGraph {
    rankdir=LR;
    node [shape=record, style="filled,rounded", fontname="Helvetica", fontsize=10];
    edge [fontname="Helvetica", fontsize=9, color="#444444", arrowhead=vee];

    Users [label="{Users | <pk> PK: user_id | github_user_id\\nlogin\\nis_bot\\nis_cohort\\nfirst_seen_at}", fillcolor="#D1E7DD", color="#0F5132"];
    Repositories [label="{Repositories | <pk> PK: repo_id | github_repo_id\\nname\\nowner_login\\norg_id\\norg_login\\nfirst_seen_at}", fillcolor="#D1E7DD", color="#0F5132"];

    PullRequests [label="{PullRequests | <pk> PK: pr_id | <fk_repo> FK: repo_id \\-\\> Repositories\\n<fk_author> FK: author_id \\-\\> Users\\n<fk_merged_by> FK: merged_by_id \\-\\> Users (known later)\\nnumber, title, draft\\nhead_ref, base_ref...}", fillcolor="#FFF3CD", color="#664D03"];
    Issues [label="{Issues | <pk> PK: issue_id | <fk_repo> FK: repo_id \\-\\> Repositories\\n<fk_author> FK: author_id \\-\\> Users\\n<fk_pr> FK: pull_request_id \\-\\> PullRequests\\n<fk_assignee> FK: assignee_id \\-\\> Users\\nnumber, title, body...}", fillcolor="#FFF3CD", color="#664D03"];
    IssueComments [label="{IssueComments | <pk> PK: comment_id | <fk_issue> FK: issue_id \\-\\> Issues\\n<fk_repo> FK: repo_id \\-\\> Repositories\\n<fk_author> FK: author_id \\-\\> Users\\nbody, created_at...}", fillcolor="#CFF4FC", color="#055160"];
    PRReviews [label="{PRReviews | <pk> PK: review_id | <fk_pr> FK: pr_id \\-\\> PullRequests\\n<fk_repo> FK: repo_id \\-\\> Repositories\\n<fk_reviewer> FK: reviewer_id \\-\\> Users\\nstate, body, submitted_at...}", fillcolor="#CFF4FC", color="#055160"];
    PRReviewComments [label="{PRReviewComments | <pk> PK: comment_id | <fk_pr> FK: pr_id \\-\\> PullRequests\\n<fk_repo> FK: repo_id \\-\\> Repositories\\n<fk_author> FK: author_id \\-\\> Users\\n<fk_review> FK: pull_request_review_id \\-\\> PRReviews\\n<fk_reply> FK: in_reply_to_id \\-\\> PRReviewComments\\npath, body, created_at...}", fillcolor="#F8D7DA", color="#842029"];
    Pushes [label="{Pushes | <pk> PK: push_id | <fk_user> FK: user_id \\-\\> Users\\n<fk_repo> FK: repo_id \\-\\> Repositories\\nref, ref_type, branch\\nis_new_ref, created_at...}", fillcolor="#E2E3E5", color="#41464B"];

    // Foreign Keys to Primary Keys
    PullRequests:fk_repo -> Repositories:pk [label="repo_id"];
    PullRequests:fk_author -> Users:pk [label="author_id"];
    PullRequests:fk_merged_by -> Users:pk [label="merged_by_id", style=dashed];

    Issues:fk_repo -> Repositories:pk [label="repo_id"];
    Issues:fk_author -> Users:pk [label="author_id"];
    Issues:fk_pr -> PullRequests:pk [label="pull_request_id"];
    Issues:fk_assignee -> Users:pk [label="assignee_id"];

    IssueComments:fk_issue -> Issues:pk [label="issue_id"];
    IssueComments:fk_repo -> Repositories:pk [label="repo_id"];
    IssueComments:fk_author -> Users:pk [label="author_id"];

    PRReviews:fk_pr -> PullRequests:pk [label="pr_id"];
    PRReviews:fk_repo -> Repositories:pk [label="repo_id"];
    PRReviews:fk_reviewer -> Users:pk [label="reviewer_id"];

    PRReviewComments:fk_pr -> PullRequests:pk [label="pr_id"];
    PRReviewComments:fk_repo -> Repositories:pk [label="repo_id"];
    PRReviewComments:fk_author -> Users:pk [label="author_id"];
    PRReviewComments:fk_review -> PRReviews:pk [label="pull_request_review_id"];
    PRReviewComments:fk_reply -> PRReviewComments:pk [label="in_reply_to_id"];

    Pushes:fk_user -> Users:pk [label="user_id"];
    Pushes:fk_repo -> Repositories:pk [label="repo_id"];
}
"""

with open("reports/schema_graph.dot", "w") as f:
    f.write(schema_dot)

print("Saved reports/schema_graph.dot")

# Render schema graph with NetworkX and Matplotlib
G_schema = nx.DiGraph()
tables = ["Users", "Repositories", "PullRequests", "Issues", "IssueComments", "PRReviews", "PRReviewComments", "Pushes"]
for t in tables:
    G_schema.add_node(t)

edges = [
    ("PullRequests", "Repositories", "repo_id"),
    ("PullRequests", "Users", "author_id"),
    ("PullRequests", "Users", "merged_by_id"),
    ("Issues", "Repositories", "repo_id"),
    ("Issues", "Users", "author_id"),
    ("Issues", "PullRequests", "pull_request_id"),
    ("Issues", "Users", "assignee_id"),
    ("IssueComments", "Issues", "issue_id"),
    ("IssueComments", "Repositories", "repo_id"),
    ("IssueComments", "Users", "author_id"),
    ("PRReviews", "PullRequests", "pr_id"),
    ("PRReviews", "Repositories", "repo_id"),
    ("PRReviews", "Users", "reviewer_id"),
    ("PRReviewComments", "PullRequests", "pr_id"),
    ("PRReviewComments", "Repositories", "repo_id"),
    ("PRReviewComments", "Users", "author_id"),
    ("PRReviewComments", "PRReviews", "pull_request_review_id"),
    ("Pushes", "Users", "user_id"),
    ("Pushes", "Repositories", "repo_id")
]

for src, dst, lbl in edges:
    G_schema.add_edge(src, dst, label=lbl)

plt.figure(figsize=(12, 8))
pos = {
    "Users": (0.1, 0.7),
    "Repositories": (0.1, 0.3),
    "PullRequests": (0.45, 0.8),
    "Issues": (0.45, 0.3),
    "PRReviews": (0.75, 0.9),
    "PRReviewComments": (0.9, 0.6),
    "IssueComments": (0.75, 0.2),
    "Pushes": (0.45, 0.05)
}
colors = ["#90EE90", "#90EE90", "#FFD700", "#FFD700", "#87CEEB", "#87CEEB", "#FFA07A", "#D3D3D3"]
nx.draw_networkx_nodes(G_schema, pos, node_size=3200, node_color=colors, edgecolors="black", linewidths=1.5)
nx.draw_networkx_labels(G_schema, pos, font_size=10, font_weight="bold")
nx.draw_networkx_edges(G_schema, pos, arrowstyle="->", arrowsize=15, edge_color="#555555", connectionstyle="arc3,rad=0.08")

plt.title("Assignment 2: Schema Graph (All 8 Tables & Foreign Keys)", fontsize=14, fontweight="bold")
plt.axis("off")
plt.tight_layout()
plt.savefig("reports/schema_graph.png", dpi=300)
plt.close()
print("Saved reports/schema_graph.png")


# ==========================================
# 2. Relational Entity Graph Generation
# ==========================================
print("Loading data for relational entity graph...")
users_df = pd.read_parquet("data/db/Users.parquet")
repos_df = pd.read_parquet("data/db/Repositories.parquet")
prs_df = pd.read_parquet("data/db/PullRequests.parquet")
issues_df = pd.read_parquet("data/db/Issues.parquet")
ic_df = pd.read_parquet("data/db/IssueComments.parquet")
prr_df = pd.read_parquet("data/db/PRReviews.parquet")
prrc_df = pd.read_parquet("data/db/PRReviewComments.parquet")
pushes_df = pd.read_parquet("data/db/Pushes.parquet")

u1, u2 = 22996444, 28983449
target_users = users_df[users_df["github_user_id"].isin([u1, u2])]
u_ids = set(target_users["user_id"].tolist())

t_start = pd.Timestamp("2026-09-15 00:00:00")
t_end = pd.Timestamp("2026-09-17 00:00:00")

# Filter events in time window for these 2 users
pushes_sub = pushes_df[(pushes_df["created_at"] >= t_start) & (pushes_df["created_at"] <= t_end) & (pushes_df["user_id"].isin(u_ids))]
ic_sub = ic_df[(ic_df["created_at"] >= t_start) & (ic_df["created_at"] <= t_end) & (ic_df["author_id"].isin(u_ids))]
prrc_sub = prrc_df[(prrc_df["created_at"] >= t_start) & (prrc_df["created_at"] <= t_end) & (prrc_df["author_id"].isin(u_ids))]
prr_sub = prr_df[(prr_df["first_seen_at"] >= t_start) & (prr_df["first_seen_at"] <= t_end) & (prr_df["reviewer_id"].isin(u_ids))]
issues_sub = issues_df[(issues_df["first_seen_at"] >= t_start) & (issues_df["first_seen_at"] <= t_end) & (issues_df["author_id"].isin(u_ids) | issues_df["assignee_id"].isin(u_ids))]
prs_sub = prs_df[(prs_df["first_seen_at"] >= t_start) & (prs_df["first_seen_at"] <= t_end) & (prs_df["author_id"].isin(u_ids) | prs_df["merged_by_id"].isin(u_ids))]

G_entity = nx.DiGraph()

# Add User nodes
for _, r in target_users.iterrows():
    node_id = f"User_{r['user_id']}"
    label = f"User {r['user_id']}\\n({r['login']}\\ngithub:{r['github_user_id']})"
    G_entity.add_node(node_id, label=label, type="User", fillcolor="#90EE90")

# Add Events and Referenced Entities
repo_nodes = set()
pr_nodes = set()
issue_nodes = set()

# Pushes
for _, r in pushes_sub.iterrows():
    p_id = f"Push_{r['push_id']}"
    G_entity.add_node(p_id, label=f"Push {r['push_id']}\\n{r['branch']}", type="Push", fillcolor="#E2E3E5")
    G_entity.add_edge(p_id, f"User_{r['user_id']}", label="user_id")
    repo_nodes.add(r['repo_id'])
    G_entity.add_edge(p_id, f"Repo_{r['repo_id']}", label="repo_id")

# PullRequests
for _, r in prs_sub.iterrows():
    pr_id = f"PR_{r['pr_id']}"
    G_entity.add_node(pr_id, label=f"PR #{r['number']}\\n(id:{r['pr_id']})", type="PR", fillcolor="#FFD700")
    if pd.notna(r['author_id']):
        G_entity.add_edge(pr_id, f"User_{int(r['author_id'])}", label="author_id")
    repo_nodes.add(r['repo_id'])
    G_entity.add_edge(pr_id, f"Repo_{r['repo_id']}", label="repo_id")

# Issues
for _, r in issues_sub.iterrows():
    iss_id = f"Issue_{r['issue_id']}"
    G_entity.add_node(iss_id, label=f"Issue #{r['number']}\\n(id:{r['issue_id']})", type="Issue", fillcolor="#FFD700")
    if pd.notna(r['author_id']):
        G_entity.add_edge(iss_id, f"User_{int(r['author_id'])}", label="author_id")
    repo_nodes.add(r['repo_id'])
    G_entity.add_edge(iss_id, f"Repo_{r['repo_id']}", label="repo_id")
    if pd.notna(r['pull_request_id']):
        pr_nodes.add(int(r['pull_request_id']))
        G_entity.add_edge(iss_id, f"PR_{int(r['pull_request_id'])}", label="pull_request_id")

# PRReviews
for _, r in prr_sub.iterrows():
    rev_id = f"PRReview_{r['review_id']}"
    G_entity.add_node(rev_id, label=f"Review {r['review_id']}\\n({r['state']})", type="PRReview", fillcolor="#87CEEB")
    G_entity.add_edge(rev_id, f"User_{r['reviewer_id']}", label="reviewer_id")
    G_entity.add_edge(rev_id, f"Repo_{r['repo_id']}", label="repo_id")
    repo_nodes.add(r['repo_id'])
    G_entity.add_edge(rev_id, f"PR_{r['pr_id']}", label="pr_id")
    pr_nodes.add(r['pr_id'])

# PRReviewComments
for _, r in prrc_sub.iterrows():
    prrc_id = f"PRReviewComment_{r['comment_id']}"
    G_entity.add_node(prrc_id, label=f"DiffComment {r['comment_id']}", type="PRReviewComment", fillcolor="#FFA07A")
    G_entity.add_edge(prrc_id, f"User_{r['author_id']}", label="author_id")
    G_entity.add_edge(prrc_id, f"Repo_{r['repo_id']}", label="repo_id")
    repo_nodes.add(r['repo_id'])
    G_entity.add_edge(prrc_id, f"PR_{r['pr_id']}", label="pr_id")
    pr_nodes.add(r['pr_id'])
    if pd.notna(r['pull_request_review_id']):
        G_entity.add_edge(prrc_id, f"PRReview_{int(r['pull_request_review_id'])}", label="review_id")

# IssueComments
for _, r in ic_sub.iterrows():
    ic_id = f"IssueComment_{r['comment_id']}"
    G_entity.add_node(ic_id, label=f"IssueComment {r['comment_id']}", type="IssueComment", fillcolor="#CFF4FC")
    G_entity.add_edge(ic_id, f"User_{r['author_id']}", label="author_id")
    G_entity.add_edge(ic_id, f"Repo_{r['repo_id']}", label="repo_id")
    repo_nodes.add(r['repo_id'])
    G_entity.add_edge(ic_id, f"Issue_{r['issue_id']}", label="issue_id")
    issue_nodes.add(r['issue_id'])

# Add Repositories
for repo_id in repo_nodes:
    repo_row = repos_df[repos_df["repo_id"] == repo_id]
    r_name = repo_row.iloc[0]["name"] if not repo_row.empty else f"Repo_{repo_id}"
    G_entity.add_node(f"Repo_{repo_id}", label=f"{r_name}\\n(repo:{repo_id})", type="Repo", fillcolor="#A3E4D7")

# Add PullRequests referenced
for pr_id in pr_nodes:
    node_name = f"PR_{pr_id}"
    if node_name not in G_entity:
        pr_row = prs_df[prs_df["pr_id"] == pr_id]
        pr_num = pr_row.iloc[0]["number"] if not pr_row.empty else pr_id
        G_entity.add_node(node_name, label=f"PR #{pr_num}\\n(id:{pr_id})", type="PR", fillcolor="#FFD700")

# Write Entity Graph DOT file
entity_dot_lines = ["digraph RelationalEntityGraph {", "    rankdir=TB;", "    node [shape=box, style=filled, fontname=\"Helvetica\", fontsize=9];", "    edge [fontname=\"Helvetica\", fontsize=8, color=\"#666666\"];"]
for n, d in G_entity.nodes(data=True):
    lbl = d.get('label', n).replace('\n', '\\n')
    fc = d.get('fillcolor', '#FFFFFF')
    entity_dot_lines.append(f'    "{n}" [label="{lbl}", fillcolor="{fc}"];')

for u, v, d in G_entity.edges(data=True):
    lbl = d.get('label', '')
    entity_dot_lines.append(f'    "{u}" -> "{v}" [label="{lbl}"];')
entity_dot_lines.append("}")

with open("reports/relational_entity_graph.dot", "w") as f:
    f.write("\n".join(entity_dot_lines))
print("Saved reports/relational_entity_graph.dot")

# Matplotlib visualization of Relational Entity Graph
plt.figure(figsize=(16, 12))
pos_entity = nx.spring_layout(G_entity, k=0.8, seed=42)
node_colors = [d.get("fillcolor", "#FFFFFF") for _, d in G_entity.nodes(data=True)]
nx.draw_networkx_nodes(G_entity, pos_entity, node_color=node_colors, node_size=2000, edgecolors="black", alpha=0.9)
node_labels = {n: d.get("label", n).replace("\\n", "\n") for n, d in G_entity.nodes(data=True)}
nx.draw_networkx_labels(G_entity, pos_entity, labels=node_labels, font_size=7, font_weight="bold")
nx.draw_networkx_edges(G_entity, pos_entity, arrowstyle="->", arrowsize=12, edge_color="#777777", alpha=0.7)

plt.title("Assignment 2: Relational Entity Graph for Users 22996444 & 28983449 (2026-09-15 to 2026-09-17 UTC)", fontsize=13, fontweight="bold")
plt.axis("off")
plt.tight_layout()
plt.savefig("reports/relational_entity_graph.png", dpi=300)
plt.close()
print("Saved reports/relational_entity_graph.png")
print("All graphs successfully generated!")
