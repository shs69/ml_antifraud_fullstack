import { type JSX } from "react";
import "./Notification.scss";
import { AnimatePresence, motion } from "motion/react";
import { useAppDispatch, useAppSelector } from "../../../app/hooks";
import { selectNotifications, showNotification } from "./NotificationSlice";
import { type Notification } from "../../../interfaces";

export const NotificationElem = (): JSX.Element => {
  const dispatch = useAppDispatch();
  const notifications = useAppSelector(selectNotifications);

  const toShow = (notification: Notification) => {
    const { id } = notification;
    dispatch(showNotification(id));
  };

  const notificationsToShow = notifications.slice(0, 5);
  notificationsToShow.forEach(toShow);

  return (
    <div className="notifications">
      <AnimatePresence>
        {notifications.length > 0 &&
          notificationsToShow.map(n => (
            <motion.div
              key={n.id}
              initial={{ opacity: 0, x: 40 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 30 }}
              transition={{ duration: 0.25, ease: "easeIn" }}
              className="notification"
            >
              <div className="notification__error_msg">
                Ошибка при добавлении операции
              </div>
              <div className="notification__msg">
                Транзакция из магазина {n.shop_name} удалена
              </div>
            </motion.div>
          ))}
      </AnimatePresence>
    </div>
  );
};
