import datetime
import sqlalchemy


class OrmConverter:

    @classmethod
    def convert_tree_to_orm(cls, tree: dict, root_type: type):
        for key, value in list(tree.items()):
            value_type = type(value)
            data_type = cls.get_nested_type(root_type, key)

            if data_type is None:
                del tree[key]
                continue

            if value is not None:
                if isinstance(data_type, sqlalchemy.Date):
                    tree[key] = datetime.date.fromisoformat(value)
                elif isinstance(data_type, sqlalchemy.DateTime):
                    if value.endswith("Z"):
                        value = value[:-1] + "+00:00"
                    tree[key] = datetime.datetime.fromisoformat(value)

                elif isinstance(data_type, sqlalchemy.types.Enum):
                    enum_class = data_type.enum_class  # type: ignore
                    try:
                        tree[key] = enum_class[  # type: ignore
                            value
                        ]  # Преобразуем строку в Enum
                    except KeyError:
                        raise ValueError(
                            f"Invalid value '{value}' for enum {enum_class}"
                        )
                elif isinstance(data_type, sqlalchemy.Boolean):
                    tree[key] = bool(value)

            if value_type is dict:
                tree[key] = cls.convert_tree_to_orm(value, data_type)
            elif value_type is list:
                tree[key] = [cls.convert_tree_to_orm(item, data_type) for item in value]

        return root_type(**tree)

    @classmethod
    def get_nested_type(cls, parent_type, field_name) -> type | None:
        if not hasattr(parent_type, field_name):
            return None

        prop = getattr(parent_type, field_name).prop
        if hasattr(prop, "mapper"):
            return prop.mapper.class_

        return prop.expression.type
