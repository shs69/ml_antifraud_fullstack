import { type JSX } from "react";
import "./Notification.scss";
import { AnimatePresence, motion } from "motion/react";
import { useAppSelector } from "../../../app/hooks";
import { selectNotifications } from "./NotificationSlice";

export const NotificationElem = (): JSX.Element => {
  const notifications = useAppSelector(selectNotifications);
  const notificationsToShow = notifications.slice(0, 5);

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
