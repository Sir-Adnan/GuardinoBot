import { useEffect, useState } from "react";
import {
  App as AntdApp,
  Alert,
  Button,
  Input,
  Skeleton,
  Space,
  Typography,
} from "antd";
import { DeleteOutlined, PlusOutlined, SaveOutlined } from "@ant-design/icons";
import { useTranslation } from "react-i18next";
import { api } from "../../providers/axios";

const { Text } = Typography;

interface Chat {
  id: string;
  username: string;
}

/**
 * Forced-join channel editor (super-admin). Each row: `id` (chat id or @username
 * the membership check uses — the bot must be admin in that chat) + `username`
 * (public username, no @, for the join link). Saves the whole set via
 * PUT /settings/force-join; the bot reloads within ~15s (settings:dirty).
 */
export function ForceJoinEditor() {
  const { t } = useTranslation();
  const { message } = AntdApp.useApp();
  const [chats, setChats] = useState<Chat[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api
      .get("/settings/force-join")
      .then((r) => setChats(r.data.chats ?? []))
      .catch(() => message.error(t("actions.failed")))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const update = (i: number, field: keyof Chat, val: string) =>
    setChats((c) => c.map((row, idx) => (idx === i ? { ...row, [field]: val } : row)));
  const add = () => setChats((c) => [...c, { id: "", username: "" }]);
  const remove = (i: number) => setChats((c) => c.filter((_, idx) => idx !== i));

  const save = async () => {
    setSaving(true);
    try {
      const r = await api.put("/settings/force-join", {
        chats: chats.filter((c) => c.id.trim() && c.username.trim()),
      });
      setChats(r.data.chats ?? []);
      message.success(t("forceJoin.saved"));
    } catch (e: any) {
      message.error(e?.response?.data?.detail || t("actions.failed"));
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <Skeleton active paragraph={{ rows: 3 }} />;

  return (
    <div>
      <Alert type="info" showIcon style={{ marginBottom: 14 }} message={t("forceJoin.hint")} />
      <div style={{ display: "grid", gap: 10 }}>
        {chats.map((c, i) => (
          <Space.Compact key={i} style={{ width: "100%" }}>
            <Input
              style={{ flex: 1.2 }}
              placeholder={t("forceJoin.id_ph")}
              value={c.id}
              onChange={(e) => update(i, "id", e.target.value)}
            />
            <Input
              style={{ flex: 1 }}
              prefix="@"
              placeholder={t("forceJoin.username_ph")}
              value={c.username}
              onChange={(e) => update(i, "username", e.target.value)}
            />
            <Button danger icon={<DeleteOutlined />} onClick={() => remove(i)} />
          </Space.Compact>
        ))}
        {chats.length === 0 && <Text type="secondary">{t("forceJoin.empty")}</Text>}
      </div>
      <Space style={{ marginTop: 14 }}>
        <Button icon={<PlusOutlined />} onClick={add}>
          {t("forceJoin.add")}
        </Button>
        <Button type="primary" icon={<SaveOutlined />} loading={saving} onClick={save}>
          {t("settings.save")}
        </Button>
      </Space>
    </div>
  );
}
