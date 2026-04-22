import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { createTask, getTasks, updateTask } from "../lib/api.js";
import { useAuth } from "../state/auth-context.jsx";

const TASKS_QUERY_KEY = ["tasks"];

export function DashboardPage() {
  const queryClient = useQueryClient();
  const { user, logout } = useAuth();
  const [newTask, setNewTask] = useState({ title: "", description: "" });

  const tasksQuery = useQuery({
    queryKey: TASKS_QUERY_KEY,
    queryFn: getTasks,
  });

  const createTaskMutation = useMutation({
    mutationFn: createTask,
    onSuccess: () => {
      setNewTask({ title: "", description: "" });
      queryClient.invalidateQueries({ queryKey: TASKS_QUERY_KEY });
    },
  });

  const toggleTaskMutation = useMutation({
    mutationFn: ({ taskId, nextStatus }) => updateTask(taskId, { status: nextStatus }),
    onMutate: async ({ taskId, nextStatus }) => {
      await queryClient.cancelQueries({ queryKey: TASKS_QUERY_KEY });
      const previousTasks = queryClient.getQueryData(TASKS_QUERY_KEY);

      queryClient.setQueryData(TASKS_QUERY_KEY, (current = []) =>
        current.map((task) =>
          task.id === taskId ? { ...task, status: nextStatus } : task,
        ),
      );

      return { previousTasks };
    },
    onError: (_error, _variables, context) => {
      if (context?.previousTasks) {
        queryClient.setQueryData(TASKS_QUERY_KEY, context.previousTasks);
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: TASKS_QUERY_KEY });
    },
  });

  const completedCount = (tasksQuery.data ?? []).filter(
    (task) => task.status === "completed",
  ).length;

  function handleCreateTask(event) {
    event.preventDefault();
    createTaskMutation.mutate({
      title: newTask.title,
      description: newTask.description || null,
      status: "pending",
    });
  }

  return (
    <main className="dashboard-shell">
      <header className="dashboard-header card">
        <div>
          <p className="eyebrow">Operations View</p>
          <h1>Enterprise task command center</h1>
          <p className="hero-copy">
            Track execution, close loops quickly, and keep the team aligned.
          </p>
        </div>

        <div className="header-actions">
          <div className="user-chip">
            <span>{user?.full_name ?? "Operator"}</span>
            <small>{user?.email}</small>
          </div>
          <button className="ghost-button" onClick={logout} type="button">
            Sign out
          </button>
        </div>
      </header>

      <section className="metrics-grid">
        <article className="metric-card card">
          <span className="metric-label">Total tasks</span>
          <strong>{tasksQuery.data?.length ?? 0}</strong>
        </article>
        <article className="metric-card card">
          <span className="metric-label">Completed</span>
          <strong>{completedCount}</strong>
        </article>
        <article className="metric-card card">
          <span className="metric-label">Cache-friendly reads</span>
          <strong>5 min TTL</strong>
        </article>
      </section>

      <section className="dashboard-grid">
        <section className="card composer-card">
          <div>
            <p className="section-label">Create task</p>
            <h2>Queue the next piece of work</h2>
          </div>

          <form className="form-grid" onSubmit={handleCreateTask}>
            <label>
              <span>Title</span>
              <input
                value={newTask.title}
                onChange={(event) =>
                  setNewTask((current) => ({ ...current, title: event.target.value }))
                }
                placeholder="Prepare quarterly delivery review"
                required
              />
            </label>

            <label>
              <span>Description</span>
              <textarea
                value={newTask.description}
                onChange={(event) =>
                  setNewTask((current) => ({ ...current, description: event.target.value }))
                }
                placeholder="Capture blockers, owners, and key milestones."
                rows={4}
              />
            </label>

            <button
              className="primary-button"
              type="submit"
              disabled={createTaskMutation.isPending}
            >
              {createTaskMutation.isPending ? "Creating..." : "Create task"}
            </button>
          </form>
        </section>

        <section className="card tasks-card">
          <div className="tasks-header">
            <div>
              <p className="section-label">Task board</p>
              <h2>Live workload</h2>
            </div>
            {tasksQuery.isFetching ? <span className="status-pill">Syncing</span> : null}
          </div>

          {tasksQuery.isLoading ? <p>Loading tasks...</p> : null}
          {tasksQuery.isError ? <p className="form-error">{tasksQuery.error.message}</p> : null}

          <div className="task-list">
            {(tasksQuery.data ?? []).map((task) => {
              const isCompleted = task.status === "completed";

              return (
                <article className={`task-item ${isCompleted ? "task-item-done" : ""}`} key={task.id}>
                  <label className="task-toggle">
                    <input
                      type="checkbox"
                      checked={isCompleted}
                      onChange={() =>
                        toggleTaskMutation.mutate({
                          taskId: task.id,
                          nextStatus: isCompleted ? "pending" : "completed",
                        })
                      }
                    />
                    <span className="check-visual" />
                  </label>

                  <div className="task-copy">
                    <h3>{task.title}</h3>
                    <p>{task.description || "No description provided."}</p>
                  </div>

                  <span className={`status-badge status-${task.status}`}>{task.status}</span>
                </article>
              );
            })}

            {!tasksQuery.isLoading && (tasksQuery.data ?? []).length === 0 ? (
              <p className="empty-state">No tasks yet. Create one to get the board moving.</p>
            ) : null}
          </div>
        </section>
      </section>
    </main>
  );
}
