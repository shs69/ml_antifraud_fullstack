import { type Middleware } from "@reduxjs/toolkit";
import {
  addNotification,
  removeNotification,
} from "../features/ui/Notification/NotificationSlice";

const timers = new Map<string, ReturnType<typeof setTimeout>>();

export const notificationsMiddleware: Middleware = store => next => action => {
  if (addNotification.match(action)) {
    const { id } = action.payload;

    const timer = setTimeout(() => {
      store.dispatch(removeNotification(id));
      timers.delete(id);
    }, 2000);

    timers.set(id, timer);
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
