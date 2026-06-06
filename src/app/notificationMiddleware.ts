import { type Middleware } from "@reduxjs/toolkit";
import {
  removeNotification,
  showNotification,
  selectNotificationById,
} from "../features/ui/Notification/NotificationSlice";
import { type RootState } from "./store";

const timers = new Map<string, ReturnType<typeof setTimeout>>();

export const notificationsMiddleware: Middleware = store => next => action => {
  if (showNotification.match(action)) {
    const id = action.payload;
    const notification = selectNotificationById(action.payload)(
      store.getState() as RootState,
    );

    if (!notification) return next(action);

    const { status } = notification;

    if (status == "queued" && !timers.has(id)) {
      const timer = setTimeout(() => {
        store.dispatch(removeNotification(id));
        timers.delete(id);
      }, 2000);

      timers.set(id, timer);
    }
  }

  if (removeNotification.match(action)) {
    const timer = timers.get(action.payload);
    if (timer) {
      clearTimeout(timer);
      timers.delete(action.payload);
    }
  }

  return next(action);
};
